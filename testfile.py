# creds_remote.py 
#WIFI_SSID = ""
#WIFI_PWD  = ""
#
#UDP_SERVER_IP = ""
#UDP_SERVER_PORT = 5018
#ID = 5656


import creds_remote
import time
from machine import Pin, I2C
import neopixel
import random


BUTTON = Pin(6, Pin.IN)

rgb_led = neopixel.NeoPixel(machine.Pin(16),1)

last_press_pin18 = 0
DEBOUNCE_MS = 50


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


led_on = machine.Timer()

#tim.init(mode=machine.Timer.ONE_SHOT, period=1000, callback=irq_handler)
def led_handler(red=0,green=0,blue=0,duty_cycl=0,repeats=4):
    #rgb_led[0] = (R, G, B)
    counter = 0
    
    def led_color():
        rgb_led[0] = (red, green, blue)
        rgb_led.write()
        
    def led_off():
        rgb_led[0] = (0, 0, 0)
        rgb_led.write()
    
    for x in repeats
        led_color()
        led_on.init(mode=machine.Timer.ONE_SHOT, period=1000, callback=led_off)
      
        
    
def led_status(message):
    pass


def irq_handler(BUTTON):
    command = None
    command = button_handler(BUTTON)
    
    if command != "action" and command != "status":
        return
       
    print(command)
    
    message = f"{creds_remote.ID},{command}"
    #received = udp_handler(message)
    
    #print(received)    
    


BUTTON.irq(handler = irq_handler, trigger=machine.Pin.IRQ_FALLING)



