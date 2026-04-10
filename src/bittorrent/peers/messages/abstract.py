from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Buffer


class AbstractPeerMessage(ABC):
    # MESSAGE_ID as a constant.
    @property
    @abstractmethod
    def MESSAGE_ID(self) -> int | None: ...


    @property
    @abstractmethod
    def length(self) -> int: ...

    @abstractmethod
    def to_bytes(self) -> bytes: ...

    @classmethod
    def from_payload(cls, data: Buffer) -> AbstractPeerMessage:
        raise NotImplementedError(
            f"{cls.__name__} does not support from_payload()"
        )

    def __repr__(self) -> str:
        payload = ", ".join(
            f"{k}={v!r}"
            for k, v in vars(self).items()
        )
        return (
            f"{type(self).__qualname__}("
            f"message_id={self.MESSAGE_ID}, "
            f"length={self.length}, "
            f"{payload}"
            ")"
        )
