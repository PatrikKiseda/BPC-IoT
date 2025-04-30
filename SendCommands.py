import machine
import time
import uselect, sys
import BG77
import _thread
import os

#funkcia na cakanie na pripojenie
def wait_for_attach(modem, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        ret = modem.sendCommand("AT+CGATT?\r\n")
        if "+CGATT: 1" in ret:
            print("ATTACHED")
            return True
        time.sleep(1)  #wait a bit before checking again
    print("Timeout waiting for network attachment.")
    return False


def setup(module):
    try:
        module.sendCommand("AT+CFUN=1\r\n")
        module.sendCommand('AT+COPS=1,2,"23003"\r\n')
        module.sendCommand('AT+CGDCONT=1,"IP","lpwa.vodafone.iot"\r\n')
        module.sendCommand("AT+CGATT=1\r\n")
        #wait_for_attach(module) 


        while not module.isRegistered():
            time.sleep(1)

        # Open socket
        success, sock = module.socket(AF_INET, SOCK_DGRAM, socket_mode=SOCK_CLIENT)
        if not success:
            raise Exception("Failed to open socket")

        # Connect to server
        if not sock.connect(ip="147.229.148.105", remote_port=7006):
            raise Exception("Failed to connect")

        #module.sendCommand('AT+QIOPEN=1,1,"UDP","147.229.148.105",7006\r\n')

        print("Module setup complete and ready for communication.")

        return sock

    except Exception as e:
        print(f"Error during setup: {e}")

#vlastna funkcia na posielanie
def send_and_receive_data(module, sock, data):
    try:
        #module.sendCommand("AT+QISEND=1,11\r\n")
        #time.sleep(1)
        #module.sendCommand(data + "\r\n")
        #time.sleep(1)

        sock.send(data)

        sock.settimeout(5)

        
        #ret = module.sendCommand("AT+QIRD=1\r\n")
        #time.sleep(1)
        
        #module.sendCommand("AT+QIRD=1\r\n")
        #time.sleep(1)
        
        #module.sendCommand("AT+QIRD=1\r\n")
        #time.sleep(1)

        length, received = sock.recv(100)
        if length > 0:
            print(f"Received {length} bytes: {received}")
        else:
            print("No response received")
          
        return received

    except Exception as e:
        print(f"Error occurred: {e}")
        return None

bg_uart = machine.UART(0, baudrate=115200, tx=machine.Pin(0), rxbuf=256, rx=machine.Pin(1), timeout = 0, timeout_char=1)

bg_uart.write(bytes("AT\r\n","ascii"))
print(bg_uart.read(10))

module = BG77.BG77(bg_uart, verbose=True, radio=False)

sock = setup(module)


#posielanie dat
data = "5656,status"
response = send_and_receive_data(module, sock, data)

time.sleep(5)

data = "5656,action"
response = send_and_receive_data(module, sock, data)











