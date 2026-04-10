from __future__ import annotations

import struct
from collections.abc import Buffer
from dataclasses import dataclass
from typing import ClassVar, Final

from .abstract import AbstractPeerMessage


@dataclass(frozen=True, slots=True)
class Cancel(AbstractPeerMessage):
    index: int
    begin: int
    block_length: int

    MESSAGE_ID: ClassVar[Final[int]] = 8
    MESSAGE_LENGTH: ClassVar[Final[int]] = 13


    @property
    def length(self) -> int:
        return self.MESSAGE_LENGTH

    def to_bytes(self) -> bytes:
        return struct.pack(
            "!IBIII",
            self.length, self.MESSAGE_ID,
            self.index, self.begin, self.block_length
        )

    @classmethod
    def from_payload(cls, payload: Buffer) -> Cancel:
        index, begin, block_length = struct.unpack_from("!III", payload)
        return cls(index, begin, block_length)
