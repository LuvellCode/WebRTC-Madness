from dataclasses import dataclass
from servers.includes.enums import MessageType


@dataclass
class HandlerSettings:
    pass_type: bool = False

message_handlers:dict[MessageType, dict[function,HandlerSettings]] = {}

def register_handler(message_type: MessageType, settings: HandlerSettings = None):
    
    def decorator(func):
        obj = {
            "func": func,
            "settings": settings if settings is not None else HandlerSettings()
        }
        message_handlers[message_type.value] = obj
        return func
    return decorator