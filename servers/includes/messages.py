import json

from dataclasses import dataclass
from servers.includes.models import User
from servers.includes.enums import MessageType


@dataclass
class BaseMessage:
    type: MessageType
    payload: dict

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "payload": self.payload
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    

"""
###
### 
###
"""

@dataclass
class ConfirmIdMessage(BaseMessage):
    """
    Message when User just connects to signaling server.
     - Server receives the User.name
     - Client receives the User.id
    """
    def __init__(self, user:User):
        super().__init__(type=MessageType.CONFIRM_ID, payload={"user": user.to_dict()})  # Can be different

@dataclass
class JoinMessage(BaseMessage):
    """
    Message when User wants to start the P2P call.
    """
    def __init__(self, user:User):
        super().__init__(type=MessageType.JOIN, payload={"user": user.to_dict()})