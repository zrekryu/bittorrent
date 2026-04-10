from __future__ import annotations

import struct
from collections.abc import Buffer
from dataclasses import dataclass
from typing import ClassVar, Final

from .abstract import AbstractPeerMessage


@dataclass(frozen=True, slots=True)
class Bitfield(AbstractPeerMessage):
    bitfield: bytes

    MESSAGE_ID: ClassVar[Final[int]] = 5


    @property
    def length(self) -> int:
        return 1 + len(self.bitfield)

    def to_bytes(self) -> bytes:
        return struct.pack(
            "!IB",
            self.length, self.MESSAGE_ID
        ) + self.bitfield

    @classmethod
    def from_payload(cls, payload: Buffer) -> Bitfield:
        bitfield: bytes = bytes(bitfield) if not isinstance(payload, bytes) else payload
        return cls(bitfield)