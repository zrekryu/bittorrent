from __future__ import annotations

import struct
from collections.abc import Buffer
from dataclasses import dataclass
from typing import ClassVar, Final

from .abstract import AbstractPeerMessage


@dataclass(frozen=True, slots=True)
class Port(AbstractPeerMessage):
    port: int

    MESSAGE_ID: ClassVar[Final[int]] = 9
    MESSAGE_LENGTH: ClassVar[Final[int]] = 3


    @property
    def length(self) -> int:
        return self.MESSAGE_LENGTH

    def to_bytes(self) -> bytes:
        return struct.pack(
            "!IBIII",
            self.length, self.MESSAGE_ID,
            self.port
        )

    @classmethod
    def from_payload(cls, payload: Buffer) -> Port:
        port: int = struct.unpack_from("!I", payload)[0]
        return cls(port)
