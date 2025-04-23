# creds.py 
#WIFI_SSID = ""
#WIFI_PWD  = ""
#
#UDP_SERVER_IP = ""
#UDP_SERVER_PORT = 5018
#ID = 5656


import network
import creds
import time
import socket
from machine import Pin, I2C
import random
import neopixel

rgb_led = neopixel.NeoPixel(machine.Pin(28),1)

BUTTON = Pin(6, Pin.IN)
LED = Pin(16, Pin.OUT)
LED.value(0)

last_press_pin18 = 0
DEBOUNCE_MS = 50

sta_if = network.WLAN(network.STA_IF) 

def _set_rgb(r: float, g: float, b: float):
    
    rgb_led[0] = (int(255 * r), int(255 * g), int(255 * b))
    rgb_led.write()


def _blink(col, on_ms=200, off_ms=200, duration_ms=0):
    start = time.ticks_ms()
    while True:
        _set_rgb(*col)            # LED ON
        time.sleep_ms(on_ms)
        _set_rgb(0, 0, 0)         # LED OFF
        time.sleep_ms(off_ms)

        if duration_ms and time.ticks_diff(time.ticks_ms(), start) >= duration_ms:
            break


# Public light-state primitives ----------------------------------------------
def gate_opening(duration_s=3):
    _blink((0, 1, 0), duration_ms=int(duration_s * 1000))


def gate_open(duration_s=3):
    _set_rgb(0, 1, 0)
    time.sleep(duration_s)
    _set_rgb(0, 0, 0)


def gate_closing(duration_s=3):
    _blink((0, 0, 1), duration_ms=int(duration_s * 1000))


def gate_closed(duration_s=3):
    _set_rgb(0, 0, 1)
    time.sleep(duration_s)
    _set_rgb(0, 0, 0)


def waiting_for_server(blink_ms=300):
    global _waiting
    _waiting = True
    try:
        while _waiting:
            _set_rgb(1, 0, 0)
            time.sleep_ms(blink_ms)
            _set_rgb(0, 0, 0)
            time.sleep_ms(blink_ms)
    finally:
        _set_rgb(0, 0, 0)


def fail_LED(duration_s=3):
    _set_rgb(1, 0, 0)
    time.sleep(duration_s)
    _set_rgb(0, 0, 0)


def stop_led():
    global _waiting
    _waiting = False
    _set_rgb(0, 0, 0)


def wlan_handler():
    if not sta_if.isconnected():
        print("WLAN is not connected")
        sta_if.active(True)
        sta_if.connect(creds.WIFI_SSID,creds.WIFI_PWD)
        while not sta_if.isconnected():
            print("Trying to establish connection")
            time.sleep(2)
    if sta_if.isconnected():
        print("WLAN connected to \'" + str(sta_if.config('ssid')) + "\' with ip " + str(sta_if.ipconfig('addr4')))
    else:
        print("WLAN not connected")

def debounce_pin(pin):
    # wait for pin to change value
    global last_press_pin18
    debouncing = 1
    active = 0
    while active < DEBOUNCE_MS:
        current_pin_state = pin.value()
        if current_pin_state == last_press_pin18:
            active += 1
        else:
            active = 0
        time.sleep_ms(1)
        last_press_pin18 = current_pin_state
    return last_press_pin18
            
        

def button_handler(button):
    global last_press_pin18
    button_start = time.ticks_ms()
    last_press_pin18 = button.value()
    pin_read = 0
    press_duration = 0
    while not pin_read:
        pin_read = debounce_pin(button)
        press_duration = time.ticks_ms() - button_start
        if press_duration > 3000:
            break
    if 200 <= press_duration <= 700:
        return "status"
    elif 900 <= press_duration <= 2000:
        return "action"

def udp_handler(data):
    waiting_for_server()  
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = random.randint(49152,65535)
    sock.bind(("0.0.0.0", port))
    
    try:
        sock.sendto(bytes(data,"ascii"),(creds.UDP_SERVER_IP,creds.UDP_SERVER_PORT))
    except:
        pass
    
    sock.settimeout(2)
    
    rec_data = []
    try:
        pre_rec_data, clientsocket = sock.recvfrom(1460)
        if clientsocket[0] == creds.UDP_SERVER_IP and clientsocket[1] == creds.UDP_SERVER_PORT:
            stop_led()
            rec_data = pre_rec_data.decode()
    except:
        pass

    sock.close()
    if rec_data:
        if rec_data == "OPENING":
            gate_opening()
        elif rec_data == "OPEN":
            gate_open()
        elif rec_data == "CLOSING":
            gate_closing()
        elif rec_data == "CLOSED":
            gate_closed()
        else:
            print("Unknown response from server:", rec_data)
    else:
        fail_LED()
    return rec_data  
    


def irq_handler(BUTTON):
    command = button_handler(BUTTON)
    #print(message)
    if command != "action" and command != "status":
        return
       
    print(command)
    
    message = f"{creds.ID},{command}"
    received = udp_handler(message)
    
    print(received)    
    


BUTTON.irq(handler = irq_handler, trigger=machine.Pin.IRQ_FALLING)


