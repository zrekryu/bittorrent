from __future__ import annotations

import struct
from collections.abc import Buffer
from dataclasses import dataclass
from typing import ClassVar, Final

from .abstract import AbstractPeerMessage


@dataclass(frozen=True, slots=True)
class Have(AbstractPeerMessage):
    index: int

    MESSAGE_ID: ClassVar[Final[int]] = 4
    MESSAGE_LENGTH: ClassVar[Final[int]] = 5


    @property
    def length(self) -> int:
        return self.MESSAGE_LENGTH

    def to_bytes(self) -> bytes:
        return struct.pack(
            "!IBI",
            self.length, self.MESSAGE_ID,
            self.index
        )

    @classmethod
    def from_payload(cls, payload: Buffer) -> Have:
        index: int = struct.unpack_from("!I", payload)[0]
        return cls(index)
