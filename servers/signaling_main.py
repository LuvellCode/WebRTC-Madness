import logging
from config import SIGNALING_HOST, SIGNALING_PORT, SIGNALING_SERVER, SSL_CONTEXT
from servers.includes.models import User
from servers.includes.enums import MessageType
from servers.includes.messages import BaseMessage, JoinMessage, ConfirmIdMessage, RTCMessage
from servers.signaling_server import signaling_server, MessageHandlerSettings

from servers.logging_config import get_logger

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)

"""
Handlers Section
"""
@signaling_server.register_handler(MessageType.CONFIRM_ID)
async def handle_confirm_id(user:User, payload:dict):
    """
    Handshake.
     1. Receive User.name
     2. Send User.id
    """
    user.name = payload.get("name")  # User name update
    signaling_server.logger.debug(f"Handshaking with user name `{user.name}`. Sending user ID `{user.id}` back.")

    message = ConfirmIdMessage(user)
    await signaling_server.send_new_message(send_to=user, message=message)

@signaling_server.register_handler(MessageType.JOIN)
async def handle_join(user:User, payload:dict):
    signaling_server.logger.debug(f"Client {user.id} wants to join with name: {user.name}")
    signaling_server.logger.debug(f"Passing the User object to all connected clients..")

    message = JoinMessage(user)
    await signaling_server.broadcast_message(user, message, include_sender=False)

@signaling_server.register_handler(MessageType.OFFER)
@signaling_server.register_handler(MessageType.ANSWER)
@signaling_server.register_handler(MessageType.CANDIDATE)
async def handle_rtc(user:User, target:User, payload:dict, message_type:MessageType):
    """
    Server doesn't modify anything in case of RTC requests, just broadcasts it to other clients.
    """
    message = RTCMessage(message_type, user, payload)
    
    await signaling_server.send_new_message(target, message)


async def run_signaling_server():
    """
    Main entry point. Sets up and starts the server
    """
    logger.info(f"Starting signaling server on {SIGNALING_SERVER}\n")
    
    # Setting up the server
    signaling_server.host = SIGNALING_HOST
    signaling_server.port = SIGNALING_PORT
    signaling_server.ssl_context = SSL_CONTEXT

    signaling_server.logger = logger

    await signaling_server.start()