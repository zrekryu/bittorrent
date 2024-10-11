import struct
import math
from typing import Iterable, Self

from .message import Message

class BitField(Message):
    MESSAGE_ID: int = 5
    
    def __init__(self: Self, data: bytearray) -> None:
        self.message_length: int = self.calc_message_length() + len(data)
        self.data = data
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(
            self.MESSAGE_FORMAT,
            self.message_length, self.MESSAGE_ID,
            ) + self.data
    
    @classmethod
    def from_bytes(cls: type[Self], payload: bytes) -> Self:
        return cls(bytearray(payload))
    
    def set_piece(self: Self, index: int) -> None:
        if index < 0 or index >= len(self.data) * 8:
            raise IndexError("Piece index out of range")
        
        piece_index: int = index // 8
        bit_index: int = index % 8
        self.data[piece_index] |= 1 << (7 - bit_index)
    
    def has_piece(self: Self, index: int) -> bool:
        if index < 0 or index >= len(self.data) * 8:
            raise IndexError("Piece index out of range")
        
        piece_index: int = index // 8
        bit_index: int = index % 8
        return self.data[piece_index] >> (7 - bit_index) != 0
    
    def iter_pieces_availability(self: Self) -> Iterable[tuple[int, bool]]:
        for byte_index, byte in enumerate(self.data):
            for bit_index in range(8):
                mask: int = 1 << (7 - bit_index)
                piece_index: int = byte_index * 8 + bit_index
                
                is_available: bool = bool(byte & mask)
                yield (piece_index, is_available)
    
    def iter_pieces(self: Self, available: bool) -> Iterable[int]:
        for byte_index, byte in enumerate(self.data):
            for bit_index in range(8):
                mask: int = 1 << (7 - bit_index)
                piece_index: int = byte_index * 8 + bit_index
                
                is_set: int = byte & mask
                if is_set and available or not is_set and not available:
                    yield piece_index
    
    @classmethod
    def create_bitfield(cls: type[Self], total_pieces: int, available: bool) -> Self:
        num_bytes: int = math.ceil(total_pieces / 8)
        
        byte_value: int = 0xFF if available else 0x00
        bitfield: bytearray = bytearray([byte_value] * num_bytes)
        
        # Set the spare bits to 0.
        used_bits: int
        if available and (used_bits := total_pieces % 8) != 0:
            bitfield[-1] &= 0xFF << (8 - used_bits)
        
        return cls(bitfield)
    
    def __repr__(self: Self) -> str:
        return (
            f"BitField("
            f"message_length={self.message_length}, "
            f"message_id={self.MESSAGE_ID}, "
            f"data={self.data!r}"
            ")"
            )