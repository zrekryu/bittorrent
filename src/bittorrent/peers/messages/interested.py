import struct
from dataclasses import dataclass
from typing import ClassVar, Final

from .abstract import AbstractPeerMessage


@dataclass(frozen=True, slots=True)
class Interested(AbstractPeerMessage):
    MESSAGE_ID: ClassVar[Final[int]] = 2
    MESSAGE_LENGTH: ClassVar[Final[int]] = 1


    def to_bytes(self) -> bytes:
        return struct.pack(
            "!IB",
            self.length, self.MESSAGE_ID
        )

    @property
    def length(self) -> int:
        return self.MESSAGE_LENGTH


INTERESTED: Final[Interested] = Interested()