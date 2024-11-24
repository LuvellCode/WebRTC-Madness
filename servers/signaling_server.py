import asyncio
from dataclasses import dataclass
import logging
from servers.includes.enums import MessageType
from servers.includes.models import User
from servers.includes.messages import BaseMessage
from servers.logging_config import get_logger
import json
import websockets


@dataclass
class MessageHandlerSettings:
    pass_type: bool = False

@dataclass
class MessageHandler:
    func: function
    settings: MessageHandlerSettings

class SignalingServer:
    def __init__(self, host, port, logger:logging.Logger=None, ssl_context=None):
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.logger = logger if logger is not None else get_logger(__name__)

        
        self.message_handlers: dict[MessageType, MessageHandler] = {}
        self.supported_message_types: set[MessageType] = set()
        self.connected_clients: dict[str, User] = {}

    """
    OPERATING
    """

    async def start(self):
        self.logger.info(f"Starting signaling server on {self.host}:{self.port}")
        async with websockets.serve(self.signaling_handler, self.host, self.port, ssl=self.ssl_context):
            await asyncio.Future()

    async def signaling_handler(self, websocket):
        """
        Main Handler
        """
        client_id = str(id(websocket))
        user = User(websocket, client_id, name=None)
        self.connected_clients[client_id] = user

        try:
            async for message in websocket:
                message = json.loads(message)
                await self.handling_middleware(user, message)
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Client {client_id} disconnected")
        finally:
            del self.connected_clients[client_id]

    async def handling_middleware(self, user:User, message:dict):

        if not isinstance(message, dict) or "type" not in message or "payload" not in message:
            self.logger.error(f"Invalid message format: {message}")
            return

        msg_type:str = message.get("type")
        payload:dict = message.get("payload")

        if msg_type not in self.supported_message_types:
            self.logger.warn(f"Unsupported message type: {msg_type}")

        handler_config = self.get_handler(msg_type)
        if handler_config is None:
            self.logger.warn(f"No handler for message type. How is it even possible?@!: {msg_type}")
            return
        try:
            func = handler_config.func
            settings:MessageHandlerSettings = handler_config.settings

            if settings.pass_type:
                await func(user, payload, msg_type)
            else:
                await func(user, payload)
            self.logger.info(f"Message {msg_type} handled successfully for user {user.name} ({user.id})")
        except Exception as e:
            self.logger.error(f"Error handling message {msg_type}: {e}")

    """
    Message registors. Are used to map MessageType -> Handler. 1:1
    """

    def register_handler(self, message_type: MessageType, func: function, settings: MessageHandlerSettings = None):
        """
        Register handler for specific type
        """
        def decorator(func):
            self.message_handlers[message_type] = MessageHandler(func=func, settings=settings or MessageHandlerSettings())
            self.supported_message_types.add(message_type)
            self.logger.debug(f"Registered handler for message type: {message_type}")
            return func
        return decorator

    def get_handler(self, message_type: MessageType) -> MessageHandler:
        """
        Get handler for specific type
        """
        return self.message_handlers.get(message_type)

    """
    Interact with clients
    """

    async def send_new_message(self, send_to:User, message:BaseMessage):
        """
        Send the message to ONE connected client.

        Server will send a message to send_to.websocket: 
        {type: MessageType, message:{...}}
        """
        if send_to.websocket.open:
            await send_to.websocket.send(message.to_json())
        else:
            self.logger.warn(f"WebSocket for client {send_to.id} ({send_to.name}) is closed.")

    async def broadcast_message(self, sender:any, message:BaseMessage, include_sender=False, from_server=False):
        """
        Send the message to ALL connected clients.

        :param sender: User or None (None for msgs from server).
        """
        tasks = []
        receivers = self.connected_clients.values()

        if from_server == True:
            include_sender = False

        receiver:User = None
        for receiver in receivers:
            if include_sender and receiver.id != sender.id:
                tasks.append(self.send_new_message(send_to=receiver, message=message))

        try:
            await asyncio.gather(*tasks, return_exceptions=False)
        except Exception as e:
            self.logger.error(f"Failed to broadcast message: {e}")


# Empty object to register handler in the future
signaling_server = SignalingServer()