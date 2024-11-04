import struct
from typing import Self

from .message import Message

class PortMessage(Message):
    MESSAGE_ID: int = 9
    PAYLOAD_FORMAT: str = "I"
    
    def __init__(self: Self, listen_port: int) -> None:
        self.message_length: int = self.calc_message_length(self.PAYLOAD_FORMAT)
        self.listen_port = listen_port
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(
            f"{self.MESSAGE_FORMAT}{self.PAYLOAD_FORMAT}",
            self.message_length, self.MESSAGE_ID,
            self.listen_port
            )
    
    @classmethod
    def from_bytes(cls: type[Self], payload: bytes) -> Self:
        return cls(struct.unpack(f">{cls.PAYLOAD_FORMAT}", payload)[0])
    
    def __repr__(self: "Port") -> str:
        return (
            f"PortMessage("
            f"message_length={self.message_length}, "
            f"message_id={self.MESSAGE_ID}, "
            f"listen_port={self.listen_port}"
            ")"
            )