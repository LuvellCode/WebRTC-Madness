import asyncio
from dataclasses import dataclass
import websockets
import json
import logging
from config import SIGNALING_HOST, SIGNALING_PORT, SIGNALING_SERVER
from servers.includes.models import User
from servers.includes.enums import MessageType
from servers.includes.messages import BaseMessage, JoinMessage, ConfirmIdMessage

from servers.server_config import server_config, MessageHandlerSettings
from servers.logging_config import get_logger


"""
Mega setup functions.
Technical etc.
"""

def log_execution(func):
    async def wrapper(*args, **kwargs):
        logger.debug(f"Executing {func.__name__} with args {args} and kwargs {kwargs}")
        return await func(*args, **kwargs)
    return wrapper

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)

async def signaling_handler(websocket):
    """
    Main Handler
    """
    client_id = str(id(websocket))
    user = User(websocket, client_id, name=None)
    server_config.connected_clients[client_id] = user

    try:
        async for message in websocket:
            message = json.loads(message)
            await handling_middleware(user, message)
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client {client_id} disconnected")
    finally:
        del server_config.connected_clients[client_id]

async def send_new_message(send_to:User, message:BaseMessage):
    """
    Send the message to ONE connected client.

    Server will send a message to send_to.websocket: 
    {type: MessageType, message:{...}}
    """
    if send_to.websocket.open:
        await send_to.websocket.send(message.to_json())
    else:
        logger.warn(f"WebSocket for client {send_to.id} ({send_to.name}) is closed.")

async def broadcast_message(sender:any, message:BaseMessage, include_sender=False, from_server=False):
    """
    Send the message to ALL connected clients.

    :param sender: User or None (None for msgs from server).
    """
    tasks = []
    receivers = server_config.connected_clients.values()

    if from_server == True:
        include_sender = False

    receiver:User = None
    for receiver in receivers:
        if include_sender and receiver.id != sender.id:
            tasks.append(send_new_message(send_to=receiver, message=message))

    try:
        await asyncio.gather(*tasks, return_exceptions=False)
    except Exception as e:
        logger.error(f"Failed to broadcast message: {e}")


async def handling_middleware(user:User, message:dict):

    if not isinstance(message, dict) or "type" not in message or "payload" not in message:
        logger.error(f"Invalid message format: {message}")
        return

    msg_type:str = message.get("type")
    payload:dict = message.get("payload")

    if msg_type not in server_config.supported_message_types:
        logger.warn(f"Unsupported message type: {msg_type}")

    handler_config = server_config.get_handler(msg_type)
    if handler_config is None:
        logger.warn(f"No handler for message type. How is it even possible?@!: {msg_type}")
        return
    try:
        func = handler_config.func
        settings:MessageHandlerSettings = handler_config.settings

        if settings.pass_type:
            await func(user, payload, msg_type)
        else:
            await func(user, payload)
        logger.info(f"Message {msg_type} handled successfully for user {user.name} ({user.id})")
    except Exception as e:
        logger.error(f"Error handling message {msg_type}: {e}")
        


"""
Handlers Section
"""

@server_config.register_handler(MessageType.CONFIRM_ID)
@log_execution
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

@server_config.register_handler(MessageType.JOIN)
@log_execution
async def handle_join(user:User, payload:dict):
    logger.info(f"Client {user.id} wants to join with name: {user.name}")
    logger.info(f"Passing the User object to all connected clients..")

    message = JoinMessage(user)
    await broadcast_message(user, message, include_sender=False)

@server_config.register_handler(MessageType.OFFER, MessageHandlerSettings(pass_type=True))
@server_config.register_handler(MessageType.ANSWER, MessageHandlerSettings(pass_type=True))
@server_config.register_handler(MessageType.CANDIDATE, MessageHandlerSettings(pass_type=True))
@log_execution
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

    logger.info(f"Starting signaling server on {SIGNALING_SERVER}\n")
    async with websockets.serve(signaling_handler, SIGNALING_HOST, SIGNALING_PORT, ssl=ssl_context):
        await asyncio.Future()  # Run forever