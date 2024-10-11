import struct
from typing import Self

class Message:
    MESSAGE_FORMAT: str = ">IB"
    
    @classmethod
    def calc_message_length(cls: type[Self], payload_format: str | None = None) -> int:
        length_format = f">B{payload_format}" if payload_format else ">B"
        return struct.calcsize(length_format)
    
    @classmethod
    def from_bytes(cls: type[Self], payload: bytes) -> Self:
        raise NotImplementedError(f"{cls.__name__} does not support from_bytes conversion")
    
    def to_bytes(self: Self) -> bytes:
        raise NotImplementedError(f"{cls.__name__}.from_bytes() must be implemented by subclasses")