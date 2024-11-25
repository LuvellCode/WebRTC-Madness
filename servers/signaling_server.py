import asyncio
from dataclasses import dataclass
import inspect
import logging
from typing import Any
from servers.includes.enums import MessageType
from servers.includes.models import User
from servers.includes.messages import BaseMessage
from servers.logging_config import get_logger
import json
import websockets


@dataclass
class MessageHandlerSettings:
    """
    Purpose: This can(!) be configured by User per handler (end dev)

    :Important: will be set a default value if not passed to a registrar
    """
    log_execution:bool = False

@dataclass
class MessageHandler:
    """
    Purpose: Configured automatically by Signaling Server
    """
    func: function
    settings: MessageHandlerSettings
    required_args: list[str]

class SignalingServer:
    SUPPORTED_HANDLER_ARGS = {"user", "payload", "message_type"}
    def __init__(self, host, port, logger:logging.Logger=None, ssl_context=None):
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.logger = logger if logger is not None else get_logger(__name__)

        
        self.message_handlers: dict[str, MessageHandler] = {}  # str: MessageType
        self.supported_message_types: set[str] = set()  # str: MessageType
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
                await self.process_message(user, message)
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Client {client_id} disconnected")
        finally:
            del self.connected_clients[client_id]

    async def process_message(self, user:User, message:dict):
        """
        Processes an incoming message, validates it, and executes the corresponding handler.
        """

        try:
            # Even if the payload is not used directly, it WILL (may) be used
            # when creating args!!!
            message_type, payload = self.validate_message_structure(message)
        except ValueError as e:
            self.logger.error(e)
            return
        
        handler_config = self.get_handler(message_type)
        if handler_config is None:
            self.logger.error(f"No handler for message type. How is it even possible?@!: {message_type}")
            return
        
        try:
            func:function = handler_config.func
            settings:MessageHandlerSettings = handler_config.settings
            
            if settings.log_execution:
                self.logger.debug(f"Executing handler `{func.__name__}` for message type: {message_type}")

            # Dynamic args building based on required_args for current handler
            # Retreive locals for each name
            args:dict[str, Any] = {key: locals().get(key) for key in handler_config.required_args}

            await func(**args)
            self.logger.info(f"Message {message_type} handled successfully for user {user.name} ({user.id})")
        except Exception as e:
            self.logger.error(f"Error in handler `{func.__name__}` for message type {message_type}: {e}")

    """
    Message registrars. Are used to map MessageType -> Handler. 1:1
    """

    def register_handler(self, message_type: MessageType, func: function, settings: MessageHandlerSettings = None):
        """
        Register handler for specific message type.
        """
        def decorator(func):
            required_args = self.validate_handler_args(func)

            if settings is None:
                settings = MessageHandlerSettings()

            self.message_handlers[message_type] = MessageHandler(func=func, settings=settings, required_args=required_args)
            self.supported_message_types.add(message_type)
            self.logger.debug(f"Registered handler for {message_type}: `{func.__name__}`")
            self.logger.debug(f"Handler args: {required_args}")
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

    """
    Validators
    """

    @staticmethod
    def validate_handler_args(handler:function) -> list[str]:
        """
        Check if all handler parameters are in SignalingServer.SUPPORTED_HANDLER_ARGS

        :returns list[str]: List of arguments
        :raises ValueError: If the handler requires arguments that are not supported.
        """
        args = list(inspect.signature(handler).parameters.keys())
        invalid_args = set(args) - SignalingServer.SUPPORTED_HANDLER_ARGS

        if invalid_args:
            raise ValueError(
                f"Handler `{handler.__name__}` for has invalid parameters: {invalid_args}. "
                f"Valid parameters are: {SignalingServer.SUPPORTED_HANDLER_ARGS}"
            )
        
        return args
    
    def validate_message_structure(self, message:dict) -> tuple[str, dict]:
        """
        Check if incoming message structure (OR MAYBE EVEN OUTCOMING OMG THIS IS CO GENERIC, i love it)

        :returns: 
            1. message_type

            2. payload
        :raises ValueError: If the message structure is invalid or unsupported.
        :rtype: tuple[str, dict]
        """

        match message:
            case {"type": str(message_type), "payload": dict(payload)}:
                if message_type not in self.supported_message_types:
                    raise ValueError(f"Unsupported message type: {message_type}")
            case _:
                raise ValueError(f"Invalid message format: {message}")
            
        return message_type, payload



# Empty object to register handler in the future
signaling_server = SignalingServer()