from __future__ import annotations

import struct
from collections.abc import Buffer
from dataclasses import dataclass
from typing import ClassVar, Final


@dataclass(frozen=True, slots=True)
class Handshake:
    reserved: bytes
    info_hash: bytes
    peer_id: bytes


    PROTOCOL_STRING_LENGTH: ClassVar[Final[int]] = 19
    PROTOCOL_STRING: ClassVar[Final[bytes]] = b"BitTorrent protocol"

    LENGTH: ClassVar[Final[int]] = 68


    def to_bytes(self) -> bytes:
        fields: list[bytes] = [
            bytes([self.PROTOCOL_STRING_LENGTH]),
            self.PROTOCOL_STRING,
            self.reserved,
            self.info_hash,
            self.peer_id
        ]
        return b"".join(fields)

    @classmethod
    def from_bytes(cls, data: Buffer) -> Handshake:
        view = memoryview(data)

        length = len(view)
        if length < cls.LENGTH:
            raise ValueError(
                f"Handshake length is too short: {length} (expected: {cls.LENGTH})"
            )

        pstrlen: int = view[0]
        if pstrlen != cls.PROTOCOL_STRING_LENGTH:
            raise ValueError(
                f"Invalid protocol string length: {pstrlen} (expected: {cls.PROTOCOL_STRING_LENGTH})"
            )

        pstr: bytes = struct.unpack_from(f"!{pstrlen}s", view, 1)[0]

        if pstr != cls.PROTOCOL_STRING:
            raise ValueError(
                f"Invalid protocol string: {pstr!r} (expected: {cls.PROTOCOL_STRING!r})"
            )

        reserved: bytes = view[20:28].tobytes()
        info_hash, peer_id = struct.unpack_from("!20s20s", view, 28)

        return cls(reserved, info_hash, peer_id)
