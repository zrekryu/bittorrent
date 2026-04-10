import struct
from dataclasses import dataclass
from typing import ClassVar, Final

from .abstract import AbstractPeerMessage


@dataclass(frozen=True, slots=True)
class KeepAlive(AbstractPeerMessage):
    MESSAGE_ID: ClassVar[Final[None]] = None
    MESSAGE_LENGTH: ClassVar[Final[int]] = 0


    def to_bytes(self) -> bytes:
        return struct.pack("!I", self.length)

    @property
    def length(self) -> int:
        return self.MESSAGE_LENGTH


KEEP_ALIVE: Final[KeepAlive] = KeepAlive()