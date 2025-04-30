# creds_remote.py 
#WIFI_SSID = ""
#WIFI_PWD  = ""
#
#UDP_SERVER_IP = ""
#UDP_SERVER_PORT = 5018
#ID = 5656

import SendCommands_v2 as nb_handler

import creds_remote
import time
from machine import Pin, I2C
import neopixel

#----------29.4--------
import ucryptolib
import uhashlib
import urandom
import struct
import json

#KEY = b'0123456789abcdef'
KEY = b'0123456789abcdef'
HMAC_KEY = b'separate-hmac-key-16'
BLOCK_SIZE = 16
#PC_IP = creds_remote.UDP_SERVER_IP  # Replace with your PC's IP

CONF_FILE = 'config.json'
last_seen_counter = -1
counter = 0

#-----------------------


BUTTON = Pin(6, Pin.IN)

rgb_led = neopixel.NeoPixel(machine.Pin(16),1)

last_press_pin18 = 0
DEBOUNCE_MS = 50


#----------29.4--------
def pad(msg):
    pad_len = BLOCK_SIZE - (len(msg) % BLOCK_SIZE)
    return msg + bytes([pad_len] * pad_len)

def unpad(padded):
    pad_len = padded[-1]
    return padded[:-pad_len]

def hmac_sha256(key, message):
    blocksize = 64
    if len(key) > blocksize:
        key = uhashlib.sha256(key).digest()
    if len(key) < blocksize:
        key = key + b'\x00' * (blocksize - len(key))
    o_key_pad = bytes([b ^ 0x5C for b in key])
    i_key_pad = bytes([b ^ 0x36 for b in key])
    inner = uhashlib.sha256(i_key_pad + message).digest()
    return uhashlib.sha256(o_key_pad + inner).digest()

def encrypt(msg):
    iv = bytes([urandom.getrandbits(1) for _ in range(len(KEY))])
    aes = ucryptolib.aes(KEY, 2, iv)
    padded = pad(msg.encode())
    ciphertext = aes.encrypt(padded)
    mac = hmac_sha256(HMAC_KEY, ciphertext)[:16]
    packet = iv + ciphertext + mac
    #sock.sendto(packet, (PC_IP, 9999))
    return packet

def decrypt_and_print(data, addr='undef'):
    
    if len(data) < 36:
        print("Packet too short, skipping")
        return
    
    iv = data[:16]
    ciphertext = data[16:-16]
    mac = data[-16:]
    
   # print("🔍 IV len:", len(iv), "Ciphertext len:", len(ciphertext), "MAC len:", len(mac))
    
    if len(ciphertext) % 16 != 0:
        print("Invalid ciphertext length from", addr)
        return
    

    expected_mac = hmac_sha256(HMAC_KEY, ciphertext)[:16]
    if mac != expected_mac:
        print("HMAC check failed from", addr)
        return

    aes = ucryptolib.aes(KEY, 2, iv)
    try:
        plaintext = unpad(aes.decrypt(ciphertext))
        last_seen_counter = counter
        return plaintext.decode()
    except:
        print("Decrypt/unpad error from", addr)
        return None

def load_config(file='config.json'):
    try:
        with open(file, 'r') as json_file:
            json_data = json.load(json_file)
            return json_data
    except:
        return 0
    
def save_config(data, file='config.json'):
    try:
        with open(file, 'w') as json_file:
            json.dump(data, json_file)
            return 1
    except:
        return 0

#-----------------------------------



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


led_off_tim = machine.Timer()
led_close_tim = machine.Timer()
counter = 0
def led_handler(red=0,green=0,blue=0,duty_cycl=0,repeats=4):
    #rgb_led[0] = (R, G, B)
    global counter
    counter = 1
    on_time = 10*duty_cycl
    off_time = 1000 - on_time
    
    def led_color():
        rgb_led[0] = (red, green, blue)
        rgb_led.write()
        
    def led_off(timer):
        rgb_led[0] = (0, 0, 0)
        rgb_led.write()
        
    def led_close(timer):
        global counter
        if counter < repeats:
            counter += 1
            led_start()
    
    def led_start():
        led_color()
        led_off_tim.init(mode=machine.Timer.ONE_SHOT, period=on_time, callback=led_off)
        led_close_tim.init(mode=machine.Timer.ONE_SHOT, period=1000, callback=led_close)
    
    led_start()
        
    
def led_status(message):
    if message == "OPEN":
        led_handler(red=0,green=255,blue=0,duty_cycl=100)
    elif message == "CLOSE":
        led_handler(red=0,green=0,blue=255,duty_cycl=100)
    elif message == "OPENING":
        led_handler(red=0,green=255,blue=0,duty_cycl=30)
    elif message == "CLOSING":
        led_handler(red=0,green=0,blue=255,duty_cycl=30)
    elif message == "ERROR":
        led_handler(red=255,green=0,blue=0,duty_cycl=50)
    

def deep_sleep(timer):
    print("Going to deep sleep")
    #time.sleep_ms(10000)
    #machine.deepsleep(10000)
    #print("Awake")
    

sleep_time = machine.Timer()
def irq_handler(BUTTON):
    command = None
    command = button_handler(BUTTON)
    
    if command != "action" and command != "status":
        return
       
    print(f"Command to server: {command}")
    message = f"{creds_remote.ID},{command}"

    msg_encrypted = encrypt(message)

    print("Encrypted (raw):", msg_encrypted)
    
    # ✅ Send raw bytes directly
    received = nb_handler.nb_handler(msg_encrypted)

    print(f"Received: {received}")
    #msg_decrypted = decrypt_and_print(received)
    
    
    msg_decrypted = "ERROR"
    ## -- dummy code ----------
    #received = "ERROR"
    #if command == "action":
    #    led_status("OPEN")
    #elif command == "status":
    #    led_status("OPENING")
    ## -- dummy code ----------
        
    
    print(f"received: {msg_decrypted}")
    led_status(msg_decrypted)
    
    
    sleep_time.init(mode=machine.Timer.ONE_SHOT, period=20000, callback=deep_sleep)




BUTTON.irq(handler = irq_handler, trigger=machine.Pin.IRQ_FALLING)

#sleep_time.init(mode=machine.Timer.ONE_SHOT, period=20000, callback=deep_sleep)


