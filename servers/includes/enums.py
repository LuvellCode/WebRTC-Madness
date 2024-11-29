from enum import Enum

class MessageType(Enum):
    CONFIRM_ID = "CONFIRM_ID"
    JOIN = "JOIN"
    CLIENTS = "CLIENTS"
    
    # WebRPC Types
    OFFER = "OFFER"
    ANSWER = "ANSWER"
    CANDIDATE = "CANDIDATE"


RTC_MESSAGE_TYPES = [
    MessageType.OFFER, MessageType.ANSWER, MessageType.CANDIDATE
]