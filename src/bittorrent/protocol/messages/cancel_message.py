import struct
from typing import Self

from .message import Message

class CancelMessage(Message):
    MESSAGE_ID: int = 8
    PAYLOAD_FORMAT: str = "III"
    
    SUPPORTS_PAYLOAD: bool = True
    
    def __init__(self: Self, index: int, begin: int, length: int) -> None:
        self.message_length: int = self.calc_message_length(self.PAYLOAD_FORMAT)
        self.index = index
        self.begin = begin
        self.length = length
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(
            f"{self.MESSAGE_FORMAT}{self.PAYLOAD_FORMAT}",
            self.message_length, self.MESSAGE_ID,
            self.index, self.begin, self.length
            )
    
    @classmethod
    def from_bytes(cls: type[Self], payload: bytes) -> Self:
        return cls(*struct.unpack(f">{cls.PAYLOAD_FORMAT}", payload))
    
    def __repr__(self: Self) -> str:
        return (
            f"CancelMessage("
            f"message_length={self.message_length}, "
            f"message_id={self.MESSAGE_ID}, "
            f"index={self.index}, "
            f"begin={self.begin}, "
            f"length={self.length}"
            ")"
            )