import struct
from typing import Self

from .message import Message

class KeepAliveMessage(Message):
    MESSAGE_ID = None
    MESSAGE_LENGTH: int = 0
    MESSAGE_FORMAT: str = ">I"
    
    SUPPORTS_PAYLOAD: bool = False
    
    def __init__(self: Self) -> None:
        self.message_length: int = self.MESSAGE_LENGTH
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(self.MESSAGE_FORMAT, self.message_length)
    
    def __repr__(self: Self) -> str:
        return f"KeepAliveMessage(message_length={self.message_length}, message_id={self.MESSAGE_ID})"