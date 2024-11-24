from enum import Enum

class MessageType(Enum):
    CONFIRM_ID = "confirmId"
    JOIN = "join"
    CLIENTS = "clients"
    
    # WebRPC Types
    OFFER = "offer"
    ANSWER = "answer"
    CANDIDATE = "candidate"

