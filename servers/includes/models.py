from dataclasses import dataclass

class User:
    def __init__(self, websocket, client_id, name=None):
        self.websocket = websocket
        self.id = client_id
        self.name = name
    
    def to_dict(self):
        return {"id": self.id, "name": self.name}
    
    def __str__(self) -> str:
        return self.to_dict().__str__()
    
    def __repr__(self) -> str:
        return f"User{self.__str__()}"