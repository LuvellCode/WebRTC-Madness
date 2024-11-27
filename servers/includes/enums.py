from enum import Enum

class MessageType(Enum):
    CONFIRM_ID = "CONFIRM_ID"
    JOIN = "JOIN"
    CLIENTS = "CLIENTS"
    
    # WebRPC Types
    OFFER = "OFFER"
    ANSWER = "ANSWER"
    CANDIDATE = "CANDIDATE"

