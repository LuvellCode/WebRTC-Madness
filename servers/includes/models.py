from dataclasses import dataclass

class User:
    def __init__(self, websocket, client_id, name=None):
        self.websocket = websocket
        self.id = client_id
        self.name = name
    
    def to_dict(self):
        return {"id": self.id, "name": self.name}