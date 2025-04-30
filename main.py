import socket
import time
from gate_sim import GarageDoor

import hmac
import hashlib
import os
# pip install pycryptodome
from Crypto.Cipher import AES
from collections import deque


KNOWN_ID = [5656]

#-----------29.4--------
KEY = b'0123456789abcdef'
HMAC_KEY = b'separate-hmac-key-16'
BLOCK_SIZE = 16

remote_msg_q = deque(maxlen=50)

def pad(msg):
    pad_len = BLOCK_SIZE - (len(msg) % BLOCK_SIZE)
    return msg + bytes([pad_len] * pad_len)

def unpad(padded):
    pad_len = padded[-1]
    return padded[:-pad_len]

def encrypt_msg(msg):
    iv = os.urandom(16)
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    padded = pad(msg.encode())
    ciphertext = cipher.encrypt(padded)

    mac = hmac.new(HMAC_KEY, ciphertext, hashlib.sha256).digest()[:16]
    packet = iv + ciphertext + mac
    #sock.sendto(packet, (PICO_IP, 8888))
    return packet

def decrypt_and_print(data, addr='undef'):
    print(f"RAW received data:{data}")
    iv = data[:16]
    ciphertext = data[16:-16]
    mac = data[-16:]

    if iv in remote_msg_q:
        print("❌ Lately used IV. Probably replayed message", addr)
        return
    else:
        remote_msg_q.append(iv)

    expected_mac = hmac.new(HMAC_KEY, ciphertext, hashlib.sha256).digest()[:16]
    if mac != expected_mac:
        print("❌ HMAC check failed from", addr)
        return

    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    try:
        plaintext = unpad(cipher.decrypt(ciphertext))
        #print("📩 From", addr, ":", plaintext.decode())
        print("From", addr, ":", plaintext.decode())
        return plaintext.decode()
    except:
        print("❌ Decrypt error from", addr)
        return None


#-----------------------



sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0",5018))

door = GarageDoor()
door.start()

while 1:
    message, client_socket = sock.recvfrom(1460)
    try:
        msg_decrypted = decrypt_and_print(message, client_socket[0])
        data = msg_decrypted.split(",")
        #print(data)
        if int(data[0]) in KNOWN_ID:
            server_response = None
            if data[1] == "status":
                server_response = door.get_status()
                #sock.sendto(bytes(server_response, "ascii"), client_socket)
            elif data[1] == "action":
                door.toggle()
                time.sleep(0.01)
                server_response = door.get_status()

            if not server_response is None:
                msg_encrypted = encrypt_msg(server_response)
                sock.sendto(msg_encrypted, client_socket)
                print(f"Message to {client_socket} >>> {server_response}")
    except Exception as err:
        print(f"Error in main while: {err}")

