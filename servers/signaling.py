import asyncio
import websockets
import json
from config import SIGNALING_HOST, SIGNALING_PORT, SIGNALING_SERVER

clients = {}

async def signaling_handler(websocket):
    """
    Обробка підключень до сигнального сервера.
    """
    client_id = str(id(websocket))
    clients[client_id] = websocket

    try:
        await notify_clients()
        async for message in websocket:
            data = json.loads(message)
            for other_id, other_ws in clients.items():
                if other_id != client_id:
                    await other_ws.send(json.dumps({**data, "clientId": client_id}))
    except websockets.exceptions.ConnectionClosed:
        print(f"[INFO] Client {client_id} disconnected")
    finally:
        del clients[client_id]
        await notify_clients()

async def notify_clients():
    """Розсилка списку підключених клієнтів."""
    message = json.dumps({
        "type": "clients",
        "clients": list(clients.keys())
    })
    await asyncio.gather(*(ws.send(message) for ws in clients.values()))

async def run_signaling_server():
    """
    Запускає сигнальний сервер.
    """
    import ssl

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    print(f"Starting signaling server on {SIGNALING_SERVER}\n")
    async with websockets.serve(signaling_handler, SIGNALING_HOST, SIGNALING_PORT, ssl=ssl_context):
        await asyncio.Future()  # Run forever