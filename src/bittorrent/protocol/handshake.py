from typing import Self
import struct

class Handshake:
    LENGTH: int = 68
    
    def __init__(
        self: Self,
        pstrlen: int,
        pstr: bytes,
        reserved: bytes,
        info_hash: bytes,
        peer_id: bytes
        ) -> None:
        self.pstrlen = pstrlen
        self.pstr = pstr
        self.reserved = reserved
        self.info_hash = info_hash
        self.peer_id = peer_id
    
    def to_bytes(self: Self) -> bytes:
        return struct.pack(
            f"B{self.pstrlen}s8s20s20s",
            self.pstrlen,
            self.pstr,
            self.reserved,
            self.info_hash,
            self.peer_id
            )
    
    @classmethod
    def from_bytes(cls: type[Self], data: bytes) -> Self:
        pstrlen: int = struct.unpack(">B", data[:1])[0]
        return cls(pstrlen, *struct.unpack(f">{pstrlen}s8s20s20s", data[1:]))
    
    def __repr__(self: Self) -> str:
        return (
            f"Handshake("
            f"pstrlen={self.pstrlen}, "
            f"pstr={self.pstr!r}, "
            f"reserved={self.reserved!r}, "
            f"info_hash={self.info_hash!r}, "
            f"peer_id={self.peer_id!r}"
            ")"
            )