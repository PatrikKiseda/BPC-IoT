import socket
import time
from gate_sim import GarageDoor
import asyncio, 
import aiocoap.resource as resource, 
import aiocoap, 
import gate_sim

KNOWN_ID = [5656]

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0",5018))

door = gate_sim.GarageDoor()
door.start()

class Gate(resource.Resource):
    async def render_post(self, request):
        cmd = request.opt.uri_path[-1]          # "action" | "status"
        if cmd == "action":
            door.toggle()
            await asyncio.sleep(0.05)
        return aiocoap.Message(payload=door.get_status().encode())

root = resource.Site();  root.add_resource(['gate', '*'], Gate())
asyncio.run(aiocoap.Context.create_server_context(root, bind=("0.0.0.0", 5683)))
asyncio.get_event_loop().run_forever()

while 1:
    message, client_socket = sock.recvfrom(1460)
    try:
        message = message.decode()
        data = message.split(",")
        print(data)
        if int(data[0]) in KNOWN_ID:
            server_response = None
            if data[1] == "status":
                server_response = door.get_status()
                sock.sendto(bytes(server_response, "ascii"), client_socket)
            elif data[1] == "action":
                door.toggle()
                time.sleep(0.01)
                server_response = door.get_status()

            if not server_response is None:
                sock.sendto(bytes(server_response, "ascii"), client_socket)
                print(f"Message to {client_socket} >>> server_response")
    except Exception as err:
        print(f"Error in main while: {err}")
