from __future__ import annotations

import struct
from collections.abc import Buffer
from dataclasses import dataclass
from typing import ClassVar, Final

from .abstract import AbstractPeerMessage


@dataclass(frozen=True, slots=True)
class Piece(AbstractPeerMessage):
    index: int
    begin: int
    block: bytes

    MESSAGE_ID: ClassVar[Final[int]] = 7

    @property
    def length(self) -> int:
        return 8 + len(self.block)

    def to_bytes(self) -> bytes:
        return struct.pack(
            "!IBII",
            self.length, self.MESSAGE_ID,
            self.index, self.begin
        ) + self.block

    @classmethod
    def from_payload(cls, payload: Buffer) -> Piece:
        view = memoryview(payload)
        index, begin = struct.unpack_from("!II", view)
        block: bytes = view[8:].tobytes()
        return cls(index, begin, block)
