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
    """
    Accepts:
      • raw bytes:   b'\x12\x34…'
      • ASCII-hex:   b'1234abcd…'
      • literal "\\x12\\x34…" string
    Converts to the true IV||cipher||MAC bytes, then does replay, HMAC & AES checks.
    """

    if isinstance(data, (bytes, bytearray)):
        try:
            txt = data.decode('ascii')
            if len(txt) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in txt):
                data = bytes.fromhex(txt)
        except UnicodeDecodeError:

            pass
    elif isinstance(data, str):
        data = data.encode('utf-8').decode('unicode_escape').encode('latin-1')

    if len(data) < 16+16:
        print("❌ Packet too short from", addr)
        return None

    iv         = data[:16]
    ciphertext = data[16:-16]
    mac        = data[-16:]

    if iv in remote_msg_q:
        print("❌ Replayed IV from", addr)
        return None
    remote_msg_q.append(iv)

    expected = hmac.new(HMAC_KEY, ciphertext, hashlib.sha256).digest()[:16]
    if mac != expected:
        print("❌ HMAC check failed from", addr)
        return None
        
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    try:
        plaintext = unpad(cipher.decrypt(ciphertext))
        text = plaintext.decode()
        print(f"📩 From {addr}:", text)
        return text
    except Exception as e:
        print("❌ Decrypt/unpad error from", addr, e)
        return None



sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0",5018))

door = GarageDoor()
door.start()

while 1:
        message, client_socket = sock.recvfrom(1460)
        try:
            hex_str = message.decode('ascii')
            raw     = bytes.fromhex(hex_str)
        except (UnicodeDecodeError, ValueError):
            raw = message
        msg_decrypted = decrypt_and_print(raw, client_socket[0])
        data = msg_decrypted.split(",")
        print(data)
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

