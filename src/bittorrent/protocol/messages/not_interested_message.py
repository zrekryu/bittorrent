import struct
from typing import Self

from .message import Message

class NotInterestedMessage(Message):
    MESSAGE_ID: int = 3
    
    SUPPORTS_PAYLOAD: bool = False
    
    def __init__(self: Self) -> None:
        self.message_length: int = self.calc_message_length()
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(
            self.MESSAGE_FORMAT,
            self.message_length, self.MESSAGE_ID
            )
    
    def __repr__(self: Self) -> str:
        return f"NotInterestedMessage(message_length={self.message_length}, message_id={self.MESSAGE_ID})"