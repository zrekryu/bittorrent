import struct
from typing import Self

from .message import Message

class PieceMessage(Message):
    MESSAGE_ID: int = 7
    PAYLOAD_FORMAT: str = "II"
    
    SUPPORTS_PAYLOAD: bool = True
    
    def __init__(self: Self, index: int, begin: int, piece: bytes) -> None:
        self.message_length: int = self.calc_message_length(self.PAYLOAD_FORMAT) + len(piece)
        self.index = index
        self.begin = begin
        self.piece = piece
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(
            f"{self.MESSAGE_FORMAT}{self.PAYLOAD_FORMAT}",
            self.message_length, self.MESSAGE_ID,
            self.index, self.begin
            ) + self.piece
    
    @classmethod
    def from_bytes(cls: type[Self], payload: bytes) -> Self:
        return cls(*struct.unpack(f">{cls.PAYLOAD_FORMAT}", payload[:8]), payload[8:])
    
    def __repr__(self: Self) -> str:
        return (
            f"PieceMessage("
            f"message_length={self.message_length}, "
            f"message_id={self.MESSAGE_ID}, "
            f"index={self.index}, "
            f"begin={self.begin}, "
            f"piece={self.piece!r}"
            ")"
            )