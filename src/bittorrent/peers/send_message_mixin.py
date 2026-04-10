from typing import Protocol

from .messages import (
    CHOKE,
    INTERESTED,
    KEEP_ALIVE,
    NOT_INTERESTED,
    UNCHOKE,
    AbstractPeerMessage,
    Bitfield,
    Cancel,
    Have,
    Piece,
    Port,
    Request,
)
from .state import PeerState


class SupportsSendMessage(Protocol):
    state: PeerState

    async def _write(self, data: bytes | bytearray) -> None: ...


class SendMessageMixin(SupportsSendMessage):
    async def send_message(self, message: AbstractPeerMessage) -> None:
        await self._write(message.to_bytes())

    async def send_keepalive(self) -> None:
        await self.send_message(KEEP_ALIVE)

    async def send_choke(self) -> None:
        await self.send_message(CHOKE)

        self.state.am_choking = True

    async def send_unchoke(self) -> None:
        await self.send_message(UNCHOKE)

        self.state.am_choking = False

    async def send_interested(self) -> None:
        await self.send_message(INTERESTED)

        self.state.am_interested = True

    async def send_not_interested(self) -> None:
        await self.send_message(NOT_INTERESTED)

        self.state.am_interested = False

    async def send_have(self, index: int) -> None:
        message = Have(index)
        await self.send_message(message)

    async def send_bitfield(self, bitfield: bytes) -> None:
        message = Bitfield(bitfield)
        await self.send_message(message)

    async def send_request(self, index: int, begin: int, block_length: int) -> None:
        message = Request(index, begin, block_length)
        await self.send_message(message)

    async def send_piece(self, index: int, begin: int, block: bytes) -> None:
        message = Piece(index, begin, block)
        await self.send_message(message)

    async def send_cancel(self, index: int, begin: int, block_length: int) -> None:
        message = Cancel(index, begin, block_length)
        await self.send_message(message)

    async def send_port(self, port: int) -> None:
        message = Port(port)
        await self.send_message(message)
