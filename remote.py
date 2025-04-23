# remote.py

import time
import neopixel
from machine import Pin, UART, Timer
import creds_remote as creds
import BG77

# socket constants from the BG77 driver
AF_INET     = BG77.AF_INET
SOCK_DGRAM  = BG77.SOCK_DGRAM
SOCK_CLIENT = BG77.SOCK_CLIENT

#===========================================================================#
#––– HARDWARE SETUP ––––––––––––––––––––––––––––––––––––––––––––––––––––––
#===========================================================================#

# NeoPixel on Pin28
rgb_led = neopixel.NeoPixel(Pin(16), 1, bpp=4)

# Physical button & fallback LED (unused, but still there)
BUTTON = Pin(6, Pin.IN)

#===========================================================================#
#––– NON-BLOCKING LED STATE MACHINE –––––––––––––––––––––––––––––––––––––
#===========================================================================#

_led_state = None
_led_timer = Timer(-1)

def _write_color(r, g, b, w):
    rgb_led[0] = (int(255*r), int(255*g), int(255*b), int(255*w))
    rgb_led.write()

def _led_blink(color, period_ms):
    # toggle between color and off
    if rgb_led[0] == (0,0,0,0):
        _write_color(*color)
    else:
        _write_color(0,0,0,0)

def _led_handler(timer):
    # called every PERIOD ms to update the LED
    if _led_state == "opening":
        _led_blink((0,1,0,0), PERIOD)
    elif _led_state == "closing":
        _led_blink((0,0,1,0), PERIOD)
    elif _led_state == "waiting":
        _led_blink((1,0,0,0), PERIOD)
    # solid states do not toggle here

def set_led(state):
    """
    state in:
      "opening", "open",
      "closing", "closed",
      "waiting", "fail", None
    """
    global _led_state
    _led_state = state

    # cancel any existing ticker
    _led_timer.deinit()

    if state in ("opening","closing","waiting"):
        # start a periodic blink
        _led_timer.init(period=PERIOD, mode=Timer.PERIODIC,
                        callback=_led_handler)
    elif state == "open":
        _write_color(0,1,0,0)
        time.sleep(DUR)           # short pause
        _write_color(0,0,0,0)
        _led_state = None
    elif state == "closed":
        _write_color(0,0,1,0)
        time.sleep(DUR)
        _write_color(0,0,0,0)
        _led_state = None
    elif state == "fail":
        _write_color(1,0,0,0)
        time.sleep(DUR)
        _write_color(0,0,0,0)
        _led_state = None
    else:
        # any other = off
        _write_color(0,0,0,0)

# you can tweak these to your taste:
PERIOD = 300   # ms blink period
DUR    = 3     # seconds for the “open”, “closed” and “fail” hold

#===========================================================================#
#––– BG77 MODEM SETUP ––––––––––––––––––––––––––––––––––––––––––––––––––––
#===========================================================================#

pwr = Pin(9, Pin.OUT, value=0)
# toggle PWRKEY high for 300ms, then low
pwr.value(1)
time.sleep_ms(300)
pwr.value(0)
# give it a couple of seconds to boot
time.sleep(2)

# 2) UART SETUP — big RX buffer so we can always read
bg_uart = UART(0,baudrate=115200,tx=Pin(0),rx=Pin(1),rxbuf=512)      # ← match their rxbuf=256, but you can use 512

# 3) PRIME THE PIPELINE: send a raw AT and read the reply
bg_uart.write(b"AT\r\n")
time.sleep_ms(200)
print("warm AT reply:", bg_uart.read(64))   # you should see b'BG77...\\r\\nOK\\r\\n'

# 4) INSTANTIATE *exactly* like in class
modem = BG77.BG77(bg_uart, verbose=True, radio=False)

# 5) now you can do your band/APN/radio bring-up
modem.sendCommand('AT+QCFG="band",0x0,0x80084,0x80084,1\r\n')
modem.setRadio(1)
modem.setAPN(creds.APN)
modem.sendCommand("AT+CIMI\r\n")
modem.sendCommand("AT+CSQ\r\n")
modem.sendCommand("AT+COPS?\r\n")
modem.sendCommand("AT+CEREG?\r\n")
modem.sendCommand("AT+QNWINFO\r\n")
print("…complete, BG77 is live")
modem.setOperator(1,"23003")
print("Attaching to NB-IoT…", end="")
if not modem.isRegistered():
    time.sleep(1)
print(" ✓ attached")

#===========================================================================#
#––– BUTTON & DEBOUNCE (unchanged) ––––––––––––––––––––––––––––––––––––––––
#===========================================================================#

last = 0
DB_MS = 50

def debounce(pin):
    global last
    stable = 0
    while stable < DB_MS:
        v = pin.value()
        if v == last:
            stable += 1
        else:
            stable = 0
        last = v
        time.sleep_ms(1)
    return last

def button_handler(pin):
    global last
    t0 = time.ticks_ms()
    last = pin.value()
    while not debounce(pin):
        if time.ticks_diff(time.ticks_ms(), t0) > 3000:
            break
    dt = time.ticks_diff(time.ticks_ms(), t0)
    if 200 <= dt <= 700:
        return "status"
    if 900 <= dt <= 2000:
        return "action"
    return None

#===========================================================================#
#––– UDP OVER NB-IOT –––––––––––––––––––––––––––––––––––––––––––––––––────
#===========================================================================#

def udp_handler(msg: str):
    set_led("waiting")

    ok, sock = modem.socket(AF_INET, SOCK_DGRAM, socket_mode=SOCK_CLIENT)
    if not ok:
        return _fail_and_return()

    if not sock.connect(creds.UDP_SERVER_IP,
                        creds.UDP_SERVER_PORT,
                        creds.UDP_PRIVATE_PORT):
        sock.close()
        return _fail_and_return()

    if not sock.send(msg):
        sock.close()
        return _fail_and_return()

    # —— wait for a stream of replies ——————————————
    sock.settimeout(5)                 # 5 s between packets
    finished = False
    t_end = time.time() + 15           # overall 15 s window

    while time.time() < t_end and not finished:
        try:
            length, data = sock.recv(1460)
        except Exception:
            break                      # timeout
        if length:
            rec = data.strip().upper()
            print("RX:", rec)
            dispatch(rec)              # update LEDs

            # stop once we hit a final state
            if rec in ("OPEN", "CLOSED"):
                finished = True

    sock.close()

    if not finished:
        return _fail_and_return()      # still in transition → treat as fail

    return rec                         # return the final state

def _fail_and_return():
    set_led("fail")
    return ""

def dispatch(state:str):
    """
    Call the right light sequence for your four states.
    """
    if   state == "OPENING": set_led("opening")
    elif state == "OPEN":    set_led("open")
    elif state == "CLOSING": set_led("closing")
    elif state == "CLOSED":  set_led("closed")
    else:                     print("Unknown reply:", state)

#===========================================================================#
#––– IRQ HANDLER & MAIN ––––––––––––––––––––––––––––––––––––––––––––––––––
#===========================================================================#

def irq_handler(pin):
    cmd = button_handler(pin)
    if not cmd: 
        return
    print("→", cmd)
    resp = udp_handler(f"{creds.ID},{cmd}")
    print("←", resp)

BUTTON.irq(handler=irq_handler, trigger=Pin.IRQ_FALLING)
