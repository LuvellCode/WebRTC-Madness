from servers.includes.enums import MessageType
from servers.includes.models import User
from dataclasses import dataclass


@dataclass
class MessageHandlerSettings:
    pass_type: bool = False

@dataclass
class MessageHandler:
    func: function
    settings: MessageHandlerSettings


# Глобальна конфігурація сервера
class ServerConfig:
    def __init__(self):
        self.message_handlers: dict[MessageType, MessageHandler] = {}
        self.supported_message_types: set[MessageType] = set()
        self.connected_clients: dict[str, User] = {}

    def register_handler(self, message_type: MessageType, func: function, settings: MessageHandlerSettings = None):
        """
        Register handler for specific type
        """
        self.message_handlers[message_type] = MessageHandler(func=func, settings=settings or MessageHandlerSettings())
        self.supported_message_types.add(message_type)

    def get_handler(self, message_type: MessageType) -> MessageHandler:
        """
        Get handler for specific type
        """
        return self.message_handlers.get(message_type)

# Singleton
server_config = ServerConfig()