import logging
from config import SIGNALING_HOST, SIGNALING_PORT, SIGNALING_SERVER
from servers.includes.models import User
from servers.includes.enums import MessageType
from servers.includes.messages import BaseMessage, JoinMessage, ConfirmIdMessage
from servers.signaling_server import signaling_server, MessageHandlerSettings

from servers.logging_config import get_logger


"""
Mega setup functions.
Technical etc.
"""

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)


def log_execution(func):
    async def wrapper(*args, **kwargs):
        logger.debug(f"Executing {func.__name__} with args {args} and kwargs {kwargs}")
        return await func(*args, **kwargs)
    return wrapper

"""
Handlers Section
"""

@signaling_server.register_handler(MessageType.CONFIRM_ID)
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
    await signaling_server.send_new_message(send_to=user, message=message)

@signaling_server.register_handler(MessageType.JOIN)
@log_execution
async def handle_join(user:User, payload:dict):
    logger.info(f"Client {user.id} wants to join with name: {user.name}")
    logger.info(f"Passing the User object to all connected clients..")

    message = JoinMessage(user)
    await signaling_server.broadcast_message(user, message, include_sender=False)

@signaling_server.register_handler(MessageType.OFFER, MessageHandlerSettings(pass_type=True))
@signaling_server.register_handler(MessageType.ANSWER, MessageHandlerSettings(pass_type=True))
@signaling_server.register_handler(MessageType.CANDIDATE, MessageHandlerSettings(pass_type=True))
@log_execution
async def handle_rtc(user:User, payload:dict, message_type:MessageType):
    message = BaseMessage(message_type, payload)
    await signaling_server.broadcast_message(user, message, include_sender=False)


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
    
    # Setting up the server
    signaling_server.host = SIGNALING_HOST
    signaling_server.port = SIGNALING_PORT
    signaling_server.logger = logger
    signaling_server.ssl_context = ssl_context

    signaling_server.start()
