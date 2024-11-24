import asyncio
from dataclasses import dataclass
import websockets
import json
from config import SIGNALING_HOST, SIGNALING_PORT, SIGNALING_SERVER
from servers.includes.models import User
from servers.includes.enums import MessageType
from servers.includes.messages import BaseMessage, JoinMessage, ConfirmIdMessage
from servers.includes.register_handler import message_handlers, HandlerSettings, register_handler

"""
Mega setup functions.
Technical etc.
"""

clients:dict[any, User] = {}

async def signaling_handler(websocket):
    """
    Main Handler
    """
    client_id = str(id(websocket))
    user = User(websocket, client_id, name=None)
    clients[client_id] = user

    try:
        async for message in websocket:
            message:dict = json.loads(message)
            await handling_middleware(user, message)

    except websockets.exceptions.ConnectionClosed:
        print(f"[INFO] Client {user.id} disconnected")
    finally:
        if client_id in clients:
            del clients[client_id]

async def send_new_message(send_to:User, message:BaseMessage):
    """
    Send the message to ONE connected client.

    Server will send a message to send_to.websocket: 
    {type: MessageType, message:{...}}
    """
    if send_to.websocket.open:
        await send_to.websocket.send(message.to_json())
    else:
        print(f"[WARN] WebSocket for client {send_to.id} ({send_to.name}) is closed.")

async def broadcast_message(sender:any, message:BaseMessage, include_sender=False, from_server=False):
    """
    Send the message to ALL connected clients.

    :param sender: User or None (None for msgs from server).
    """
    tasks = []
    receivers = clients.values()

    if from_server == True:
        include_sender = False

    receiver:User = None
    for receiver in receivers:
        if include_sender and receiver.id != sender.id:
            tasks.append(send_new_message(send_to=receiver, message=message))

    try:
        await asyncio.gather(*tasks, return_exceptions=False)
    except Exception as e:
        print(f"[ERROR] Failed to broadcast message: {e}")


async def handling_middleware(user:User, message:dict):

    if not isinstance(message, dict) or "type" not in message or "payload" not in message:
        print(f"[ERROR] Invalid message format: {message}")
        return

    msg_type:str = message.get("type")
    payload:dict = message.get("payload")

    handler = message_handlers.get(msg_type)
    if handler:
        func = handler["func"]
        settings:HandlerSettings = handler["settings"]

        if settings.pass_type:
            await func(user, payload, msg_type)
        else:
            await func(user, payload)
    else:
        print(f"[WARN] No handler for message type: {msg_type}")


"""
Handlers Section
"""


@register_handler(MessageType.CONFIRM_ID)
async def handle_confirm_id(user:User, payload:dict):
    """
    Handshake.
     1. Receive User.name
     2. Send User.id
    """
    user.name = payload.get("name")  # User name update
    print(f"Handshaking with `{user.name}`. Sending ID {user.id} back.")

    message = ConfirmIdMessage(user)
    await send_new_message(send_to=user, message=message)

@register_handler(MessageType.JOIN)
async def handle_join(user:User, payload:dict):
    print(f"[INFO] Client {user.id} wants to join with name: {user.name}")
    print(f"Passing the User object to all connected clients..")

    message = JoinMessage(user)
    await broadcast_message(user, message, include_sender=False)

@register_handler(MessageType.OFFER, HandlerSettings(pass_type=True))
@register_handler(MessageType.ANSWER, HandlerSettings(pass_type=True))
@register_handler(MessageType.CANDIDATE, HandlerSettings(pass_type=True))
async def handle_rtc(user:User, payload:dict, message_type:MessageType):
    message = BaseMessage(message_type, payload)
    await broadcast_message(user, message, include_sender=False)


"""
Other Functions
"""

async def run_signaling_server():
    """
    Main entry point. Starts the server
    """
    import ssl

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    print(f"Starting signaling server on {SIGNALING_SERVER}\n")
    async with websockets.serve(signaling_handler, SIGNALING_HOST, SIGNALING_PORT, ssl=ssl_context):
        await asyncio.Future()  # Run forever