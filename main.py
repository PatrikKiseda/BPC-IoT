import socket
import time
from gate_sim import GarageDoor

import hmac
import hashlib
import os
from Crypto.Cipher import AES
from collections import deque


KNOWN_ID = [5656]

# ---- AES / HMAC config ----
KEY = b'0123456789abcdef'
HMAC_KEY = b'separate-hmac-key-16'
BLOCK_SIZE = 16
remote_msg_q = deque(maxlen=50)

# ---- Crypto helpers ----
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
    return iv + ciphertext + mac

def decrypt_and_print(data, addr='undef'):
    print(f"\n🔍 Received raw data from {addr}: {data}")

    # Try to interpret data as ASCII hex
    if isinstance(data, (bytes, bytearray)):
        try:
            txt = data.decode('ascii')
            if len(txt) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in txt):
                print("ℹ️ Detected ASCII-hex input")
                data = bytes.fromhex(txt)
        except UnicodeDecodeError:
            print("ℹ️ Binary input detected (not ASCII)")

    elif isinstance(data, str):
        print("ℹ️ Decoding Python string with escape sequences")
        data = data.encode('utf-8').decode('unicode_escape').encode('latin-1')

    if len(data) < 32:
        print(f"❌ Packet too short from {addr} (length: {len(data)})")
        return None

    iv         = data[:16]
    ciphertext = data[16:-16]
    mac        = data[-16:]

    print(f"🧩 IV: {iv.hex()}")
    print(f"🔐 Ciphertext: {ciphertext.hex()}")
    print(f"🔏 MAC: {mac.hex()}")

    if iv in remote_msg_q:
        print(f"❌ Replayed IV from {addr}")
        return None
    remote_msg_q.append(iv)

    expected_mac = hmac.new(HMAC_KEY, ciphertext, hashlib.sha256).digest()[:16]
    if mac != expected_mac:
        print(f"❌ HMAC mismatch from {addr}")
        print(f"📛 Expected: {expected_mac.hex()}")
        return None

    try:
        cipher = AES.new(KEY, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext))
        text = plaintext.decode()
        print(f"✅ Decrypted message from {addr}: {text}")
        return text
    except Exception as e:
        print(f"❌ Decrypt/unpad error from {addr}: {e}")
        return None

# ---- UDP setup and garage door sim ----
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5018))

door = GarageDoor()
door.start()

print("🚀 UDP server running on port 5018")

while True:
    try:
        message, client_socket = sock.recvfrom(1460)

        # Attempt decoding if ASCII hex, else raw
        try:
            hex_str = message.decode('ascii')
            raw = bytes.fromhex(hex_str)
        except (UnicodeDecodeError, ValueError):
            raw = message

        msg_decrypted = decrypt_and_print(raw, client_socket[0])
        if msg_decrypted is None:
            continue

        data = msg_decrypted.split(",")
        print(f"🧾 Parsed message: {data}")

        if int(data[0]) in KNOWN_ID:
            server_response = None
            if data[1] == "status":
                server_response = door.get_status()
            elif data[1] == "action":
                door.toggle()
                time.sleep(0.01)
                server_response = door.get_status()

            if server_response is not None:
                msg_encrypted = encrypt_msg(server_response)
                sock.sendto(msg_encrypted, client_socket)
                print(f"📤 Sent response to {client_socket} → {server_response}")

    except Exception as err:
        print(f"💥 Error in main loop: {err}")
