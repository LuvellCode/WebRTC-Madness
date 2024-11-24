from servers.includes.enums import MessageType
from servers.includes.models import User
from servers.includes.messages import BaseMessage
from dataclasses import dataclass
from typing import Callable, Dict

"""
!!!WORK IN PROGRESS!!!
"""


@dataclass
class MessageHandlerSettings:
    pass_type: bool = False

@dataclass
class MessageHandler:
    func: Callable
    settings: MessageHandlerSettings


# Глобальна конфігурація сервера
class ServerConfig:
    def __init__(self):
        self.message_handlers: Dict[MessageType, MessageHandler] = {}
        self.supported_message_types: set[MessageType] = set()
        self.connected_clients: Dict[str, User] = {}

    def register_handler(self, message_type: MessageType, func: Callable, settings: dict = None):
        """
        Register handler for type
        """
        self.message_handlers[message_type] = MessageHandler(func=func, settings=settings or {})
        self.supported_message_types.add(message_type)

    def get_handler(self, message_type: MessageType) -> MessageHandler:
        """
        Get handler for type
        """
        return self.message_handlers.get(message_type)

# Singleton
server_config = ServerConfig()