import struct
from typing import Self

from .message import Message

class Have(Message):
    MESSAGE_ID: int = 4
    PAYLOAD_FORMAT: str = "I"
    
    def __init__(self: Self, index: int) -> None:
        self.message_length: int = self.calc_message_length(self.PAYLOAD_FORMAT)
        self.index = index
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(
            f"{self.MESSAGE_FORMAT}{self.PAYLOAD_FORMAT}",
            self.message_length, self.MESSAGE_ID,
            self.index
            )
    
    @classmethod
    def from_bytes(cls: type[Self], payload: bytes) -> Self:
        return cls(*struct.unpack(f">{cls.PAYLOAD_FORMAT}", payload))
    
    def __repr__(self: Self) -> str:
        return (
            f"Have("
            f"message_length={self.message_length}, "
            f"message_id={self.MESSAGE_ID}, "
            f"index={self.index}"
            ")"
            )