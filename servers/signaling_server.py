import asyncio
from dataclasses import dataclass
import inspect
import logging
from typing import Any, Callable
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
    log_execution:bool = True

@dataclass
class MessageHandler:
    """
    Purpose: Configured automatically by Signaling Server
    """
    func: Callable
    settings: MessageHandlerSettings
    required_args: list[str]

class SignalingServer:

    SUPPORTED_HANDLER_ARGS = {"user", "payload", "message_type"}
    """ A whitelist for locals(). All other vars will not be passed"""

    def __init__(self, host=None, port=None, logger:logging.Logger=None, ssl_context=None):
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

        self.log_registered_handlers()

        async with websockets.serve(self.signaling_handler, self.host, self.port, ssl=self.ssl_context):
            await asyncio.Future()

    def log_registered_handlers(self):
        """
        Log all registered handlers in a readable format.
        """
        self.logger.debug("Registered Handlers:")
        for message_type, handler in self.message_handlers.items():
            self.logger.debug(
                f"\n\tMessage Type:\t\t {message_type}\n"
                f"\tHandler Function:\t {handler.func.__name__}\n"
                f"\tRequired Args:\t\t {handler.required_args}\n"
                f"\tSettings:\t\t {handler.settings}\n"
            )

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
            func:Callable = handler_config.func
            settings:MessageHandlerSettings = handler_config.settings
            
            # if settings.log_execution:
            self.logger.info(f"Executing handler `{func.__name__}` for message type: {message_type}")

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

    def register_handler(self, message_type: MessageType, settings: MessageHandlerSettings = None):
        """
        Register handler for specific message type.
        """
        def decorator(func, settings=settings):
            required_args = self.validate_handler_args(func)

            if settings is None:
                settings = MessageHandlerSettings()

            self.message_handlers[message_type] = MessageHandler(func=func, settings=settings, required_args=required_args)
            self.supported_message_types.add(message_type)
            self.logger.debug(f"Registered handler for {message_type}: {func.__name__}: {required_args}")
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
        self.logger.debug(f"Sending message to {send_to.name} ({send_to.id}): {message.to_json()}")
        await send_to.websocket.send(message.to_json())

    async def broadcast_message(self, sender:any, message:BaseMessage, include_sender=False, from_server=False):
        """
        Send the message to ALL connected clients.

        :param sender: User or None (None for msgs from server).
        """
        tasks = []
        receivers = list(self.connected_clients.values())        

        if from_server == True:
            include_sender = False

        if not include_sender and not from_server:
            receivers = [receiver for receiver in receivers if receiver != sender]
        
        self.logger.debug(f"{receivers=}")
        receiver:User = None
        for receiver in receivers:
            tasks.append(self.send_new_message(send_to=receiver, message=message))

        try:
            self.logger.debug(f"Tasks: {tasks}")
            await asyncio.gather(*tasks, return_exceptions=False)
        except Exception as e:
            self.logger.error(f"Failed to broadcast message: {e}")

    """
    Validators
    """

    @staticmethod
    def validate_handler_args(handler:Callable) -> list[str]:
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

                try:
                    message_type = MessageType(message_type)
                except:
                    self.logger.error(f"Could not convert {message_type} to MessageType() enum object")
                    raise ValueError(f"Invalid message type: {message_type}")

                if message_type not in self.supported_message_types:
                    self.logger.error(f"Message type {message_type} is not within the support message types. Allowed types: {self.supported_message_types}")
                    raise ValueError(f"Unsupported message type: {message_type}")
                
            case _:
                raise ValueError(f"Invalid message format: {message}")
            
        return message_type, payload


logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)
# Empty object to register handler in the future
signaling_server = SignalingServer(logger=logger)