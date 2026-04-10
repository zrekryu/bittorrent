import asyncio

from bittorrent.types import PeerMessageQueue

from ..peers import MessageDispatcher, PeerConnection
from ..peers.messages import AbstractPeerMessage, Bitfield, Have


class PieceManager:
    def __init__(
        self,
        message_queue: PeerMessageQueue,
        availability_map: PieceAvailabilityMap
    ) -> None:
        self.message_queue = message_queue
        self.availability_map = availability_map

        self._running = False
        self._read_task: asyncio.Task[None] | None = None

    @staticmethod
    def create_message_queue(dispatcher: MessageDispatcher) -> PeerMessageQueue:
        message_queue: PeerMessageQueue = asyncio.Queue()
        dispatcher.add_message_queue(AbstractPeerMessage, message_queue)
        return message_queue

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Piece manager is already running")

        self._read_task = asyncio.create_task(self._read_worker)

    async def stop(self) -> None:
        if not self.is_running:
            return

        self._running = False
        assert self._read_task is not None

        self.message_queue.shutdown()

        await self._read_task
        self._read_task = None

    async def _read_worker(self) -> None:
        while True:
            try:
                peer, message = await self.message_queue.get()
            except asyncio.QueueShutDown:
                break

            self._handle_message(peer, message)

    def _handle_message(peer: PeerConnection, message: AbstractPeerMessage) -> None:
        if isinstance(message, Have):
            self._handle_have_message(peer, message)
        elif isinstance(message, Bitfield):
            self._handle_bitfield_message(peer, message)

    def _handle_have_message(peer: PeerConnection, have: Have) -> None:
        self.availability_map.add_peer(have.index, peer.peer_id)

    def _handle_bitfield_message(peer: PeerConnection, bitfield: Bitfield) -> None:
        self.availability_map.set_peer_pieces(peer.peer_id, peer.bitfield.get_pieces_availability())
