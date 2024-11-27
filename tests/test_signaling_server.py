import asyncio
import websockets
import json
import sys, os, ssl, random

# Adding root reference
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from config import SIGNALING_HOST, SIGNALING_PORT, SIGNALING_SERVER, SSL_CONTEXT

async def test_signaling_server():
    uri = SIGNALING_SERVER

    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_verify_locations("server.crt")  # Вкажіть шлях до вашого сертифіката
    ssl_context.check_hostname = False  # Не перевіряти ім'я хоста
    ssl_context.verify_mode = ssl.CERT_REQUIRED  # Вимагати сертифікат

    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        
        
        await websocket.send(json.dumps({"type": "CONFIRM_ID", "payload": {"name": f"TestUser{random.randint(0,100)}"}}))
        response = await websocket.recv()
        print(f"Server response: {response}")

        
        await websocket.send(json.dumps({"type": "JOIN", "payload": {}}))
        response = await websocket.recv()
        print(f"Server response: {response}")

        # Not expected. TBD
        # await websocket.send(json.dumps({"type": "OFFER", "payload": {"sdp": "fake-sdp-offer"}}))
        # response = await websocket.recv()
        # print(f"Server response: {response}")

asyncio.run(test_signaling_server())
