
import json
from aiortc import RTCPeerConnection, RTCDataChannel
from dataclasses import dataclass, field

from .BetterLog import BetterLog

@dataclass
class BaseClient(BetterLog):
    name: str
    id: int = None

    def to_dict(self) -> dict:
        return {"name": self.name, "id": self.id}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @staticmethod
    def from_payload(user_dict):
        return BaseClient(name=user_dict["name"], id=user_dict["id"])

@dataclass
class RemoteClient(BaseClient):
    peerConnection: RTCPeerConnection = None
    data_channel:RTCDataChannel = None

    @staticmethod
    def from_payload(user_dict):
        return RemoteClient(name=user_dict["name"], id=user_dict["id"])
    

class LocalClient(BaseClient):
    def __init__(self, name, id = None):
        super().__init__(name, id)
        self.remotePeers: dict[int, RemoteClient] = {}

    @staticmethod
    def from_payload(user_dict):
        raise NotImplementedError()