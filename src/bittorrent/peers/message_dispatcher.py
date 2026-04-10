import asyncio
from collections import defaultdict

from bittorrent.types import PeerMessageQueue

from .connection import PeerConnection
from .messages import AbstractPeerMessage


class PeerMessageDispatcher:
    def __init__(self) -> None:
        self._message_queue: PeerMessageQueue = asyncio.Queue()

        self._message_queues: dict[type[AbstractPeerMessage], list[PeerMessageQueue]] = defaultdict(list)

        self._running: bool = False
        self._read_task: asyncio.Task[None] | None = None

    @property
    def message_queue(self) -> PeerMessageQueue:
        return self._message_queue

    @property
    def is_running(self) -> bool:
        return self._running

    def add_message_queue(
        self,
        message_type: type[AbstractPeerMessage],
        message_queue: PeerMessageQueue
    ) -> None:
        self._message_queues[message_type].append(message_queue)

    def remove_message_queue(
        self,
        message_type: type[AbstractPeerMessage],
        message_queue: PeerMessageQueue
    ) -> None:
        queues = self._message_queues.get(message_type)
        if not queues:
            return

        try:
            queues.remove(message_queue)
        except ValueError:
            pass

        if not queues:
            del self._message_queues[message_type]

    async def _read_worker(self) -> None:
        while True:
            try:
                peer, message = await self._message_queue.get()
            except asyncio.QueueShutDown:
                break

            await self._broadcast_peer_message(peer, message)

    async def _broadcast_peer_message(self, peer: PeerConnection, message: AbstractPeerMessage) -> None:
        queues = self._message_queues[type(message)]
        if not queues:
            return

        await asyncio.gather(*(queue.put((peer, message)) for queue in queues))

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Rounter already running")

        self._running = True
        self._read_task = asyncio.create_task(self._read_worker())

    async def stop(self) -> None:
        if not self.is_running:
            return

        self._running = False
        assert self._read_task is not None

        self._message_queue.shutdown()

        await self._read_task
        self._read_task = None