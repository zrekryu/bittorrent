from __future__ import annotations

import asyncio
import struct
from typing import ClassVar, Final

from bittorrent.exceptions import (
    PeerConnectionError,
    PeerConnectionTimeout,
    PeerHandshakeError,
)
from bittorrent.types import PeerMessageTuple

from .bitfield import PeerBitfield
from .handshake import Handshake
from .message_parser import parse_message
from .messages import (
    CHOKE,
    INTERESTED,
    KEEP_ALIVE,
    NOT_INTERESTED,
    UNCHOKE,
    Bitfield,
    Have,
)
from .send_message_mixin import SendMessageMixin
from .source import UNKNOWN_PEER_SOURCE, PeerSource
from .state import PeerState


class PeerConnection(SendMessageMixin):
    CONNECT_TIMEOUT: ClassVar[Final[int]] = 10
    HANDSHAKE_TIMEOUT: ClassVar[Final[int]] = 15
    READ_TIMEOUT: ClassVar[Final[int]] = 120
    WRITE_KEEPALIVE_TIMEOUT: ClassVar[Final[int]] = 60

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        address: tuple[str, int],
        handshake: Handshake,
        bitfield: PeerBitfield,
        message_queue: asyncio.Queue[PeerMessageTuple],
        source: PeerSource | None = None,
        read_timeout: int | None = None,
        write_keepalive_timeout: int | None = None
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.address = address
        self.handshake: Handshake = handshake
        self.bitfield = bitfield
        self.message_queue = message_queue
        self.source = source or UNKNOWN_PEER_SOURCE
        self.read_timeout = read_timeout or self.READ_TIMEOUT
        self.write_keepalive_timeout = write_keepalive_timeout or self.WRITE_KEEPALIVE_TIMEOUT

        self._closed: bool = False

        self._read_task: asyncio.Task[None] = asyncio.create_task(self._read_worker())

        self._write_queue: asyncio.Queue[bytes | bytearray] = asyncio.Queue()
        self._write_task: asyncio.Task[None] = asyncio.create_task(self._write_worker())

        self._write_keepalive_event: asyncio.Event = asyncio.Event()
        self._write_keepalive_task: asyncio.Task[None] = asyncio.create_task(self._write_keepalive_worker())

        self.state: PeerState = PeerState()

    @staticmethod
    async def _handshake(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        handshake: Handshake,
        timeout: int
    ) -> Handshake:
        writer.write(handshake.to_bytes())
        await writer.drain()

        try:
            handshake_bytes: bytes = await asyncio.wait_for(
                reader.readexactly(Handshake.LENGTH),
                timeout=timeout
            )
        except TimeoutError:
            raise PeerHandshakeError("Peer handshake timed out")
        except asyncio.IncompleteReadError:
            raise PeerHandshakeError("Peer closed reading before finishing handshake")

        try:
            peer_handshake: Handshake = Handshake.from_bytes(handshake_bytes)
        except ValueError as exc:
            raise PeerHandshakeError(exc) from exc

        if peer_handshake.info_hash != handshake.info_hash:
            raise PeerHandshakeError(
                f"Peer handshake info hash does not match: {peer_handshake.info_hash!r} "
                f"(expected: {handshake.info_hash!r})"
            )

        return peer_handshake

    @classmethod
    async def connect(
        cls,
        address: tuple[str, int],
        handshake: Handshake,
        num_pieces: int,
        message_queue: asyncio.Queue[PeerMessageTuple],
        source: PeerSource | None = None,
        read_timeout: int | None = None,
        write_keepalive_timeout: int | None = None,
        connect_timeout: int | None = None,
        handshake_timeout: int | None = None
    ) -> PeerConnection:
        connect_timeout = connect_timeout or cls.CONNECT_TIMEOUT
        handshake_timeout = handshake_timeout or cls.HANDSHAKE_TIMEOUT

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(*address),
                timeout=connect_timeout
            )
        except TimeoutError:
            raise PeerConnectionTimeout(f"Connection timed out for {address}")
        except Exception as exc:
            raise PeerConnectionError(f"Failed to connect to {address}: {exc}")

        peer_handshake: Handshake = await cls._handshake(
            reader, writer, handshake, handshake_timeout
        )

        return cls(
            reader=reader,
            writer=writer,
            handshake=peer_handshake,
            bitfield=PeerBitfield.create(num_pieces),
            address=address,
            message_queue=message_queue,
            source=source,
            read_timeout=read_timeout,
            write_keepalive_timeout=write_keepalive_timeout
        )

    @property
    def is_closed(self) -> bool:
        return self._closed

    async def _read_message_length(self) -> int:
        length_bytes = await self.reader.readexactly(4)
        return struct.unpack("!I", length_bytes)[0]

    async def _read_message_id(self) -> int:
        message_id_bytes = await self.reader.readexactly(1)
        return struct.unpack("!B", message_id_bytes)[0]

    async def _read_message_payload(self, length: int) -> bytes:
        return await self.reader.readexactly(length)

    async def _read_messages(self) -> None:
        message_length: int = await self._read_message_length()

        message_id: int | None = None
        payload: bytes | None = None

        if message_length > 0:
            message_id = await self._read_message_id()
            payload = await self._read_message_payload(message_length - 1)

        await self._handle_message(message_length, message_id, payload)

    async def _read_worker(self) -> None:
        try:
            while not self.is_closed:
                await asyncio.wait_for(self._read_messages(), timeout=self.read_timeout)
        except TimeoutError:
            await self.close()
        except asyncio.IncompleteReadError:
            await self.close()

    async def _write(self, data: bytes | bytearray) -> None:
        await self._write_queue.put(data)

    async def _write_worker(self) -> None:
        while True:
            try:
                data: bytes = await self._write_queue.get()
            except asyncio.QueueShutDown:
                break

            self.writer.write(data)
            self._write_keepalive_event.set()

            try:
                await self.writer.drain()
            except (
                BrokenPipeError,
                ConnectionResetError,
                ConnectionAbortedError
            ):
                await self.close()
                break

    async def _write_keepalive_worker(self) -> None:
        while not self.is_closed:
            try:
                await asyncio.wait_for(
                    self._write_keepalive_event.wait(),
                    timeout=self.write_keepalive_timeout
                )
            except TimeoutError:
                await self.send_keepalive()
            else:
                self._write_keepalive_event.clear()

    async def _handle_message(
        self,
        message_length: int = 0,
        message_id: int | None = None,
        payload: bytes | None = None
    ) -> None:
        message = parse_message(message_length, message_id, payload)

        if message is KEEP_ALIVE:
            pass
        elif message is CHOKE:
            self.state.choking = True
        elif message is UNCHOKE:
            self.state.choking = False
        elif message is INTERESTED:
            self.state.interested = True
        elif message is NOT_INTERESTED:
            self.state.interested = False
        elif isinstance(message, Have):
            self.bitfield.set_piece(message.index)
        elif isinstance(message, Bitfield):
            if len(message.bitfield) != self.bitfield.num_bytes:
                pass
            else:
                self.bitfield.set_data(message.bitfield)

        await self.message_queue.put((self, message))

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        self._write_queue.shutdown()
        await self._write_task

        self._write_keepalive_event.set()
        await self._write_keepalive_task

        self.writer.close()
        await self.writer.wait_closed()

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}("
            f"address={self.address}, "
            f"source={self.source}, "
            f"peer_id={self.handshake.peer_id!r}, "
            f"state={self.state}"
            ")"
        )
