import asyncio
import logging
from collections.abc import Sequence
from contextlib import suppress
from typing import ClassVar, Final

from bittorrent.exceptions import HTTPTrackerError, UDPTrackerError
from bittorrent.peers import PeerManager
from bittorrent.types import TrackerClient, TrackerResponse

from .clients.http import HTTPTrackerClient
from .clients.udp import UDPTrackerClient

logger = logging.getLogger(__name__)


class PeriodicTrackerAnnouncer:
    INTERVAL: ClassVar[Final[int]] = 120

    def __init__(
        self,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        peer_manager: PeerManager,
        compact: bool = True,
        ipv6: bool = False,
        ip: str | None = None,
        http_tracker_timeout: int | None = HTTPTrackerClient.TIMEOUT,
        udp_tracker_timeout: int = UDPTrackerClient.TIMEOUT,
        udp_tracker_retry_backoff_factor: int = UDPTrackerClient.RETRY_BACKOFF_FACTOR,
        udp_tracker_max_retries: int = UDPTrackerClient.MAX_RETRIES,
        interval: int = INTERVAL,
        follow_response_interval: bool = True,
    ) -> None:
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.port = port

        self.peer_manager = peer_manager

        self.compact = compact
        self.ipv6 = ipv6
        self.ip = ip

        self.http_tracker_timeout = http_tracker_timeout

        self.udp_tracker_timeout = udp_tracker_timeout
        self.udp_tracker_retry_backoff_factor = udp_tracker_retry_backoff_factor
        self.udp_tracker_max_retries = udp_tracker_max_retries

        self.interval = interval
        self.follow_response_interval = follow_response_interval

        self._announce_tasks: dict[TrackerClient, asyncio.Task[None]] = {}
        self._response_queue: asyncio.Queue[tuple[TrackerClient, TrackerResponse]] = asyncio.Queue()

    async def _announce_http_tracker(self, tracker: HTTPTrackerClient, interval: int | None = None) -> None:
        interval = interval or self.interval

        while True:
            await asyncio.sleep(interval)

            try:
                response = await tracker.announce(
                    info_hash=self.info_hash,
                    peer_id=self.peer_id,
                    port=self.port,
                    uploaded=self.peer_manager.uploaded,
                    downloaded=self.peer_manager.downloaded,
                    left=self.peer_manager.left,
                    compact=self.compact,
                    ipv6=self.ipv6,
                    ip=self.ip,
                    timeout=self.http_tracker_timeout
                )
            except HTTPTrackerError as exc:
                logger.error(exc)
                continue

            await self._response_queue.put((tracker, response))

    async def _announce_udp_tracker(self, tracker: UDPTrackerClient, interval: int | None = None) -> None:
        interval = interval or self.interval

        while True:
            await asyncio.sleep(interval)

            try:
                response = await tracker.announce(
                    info_hash=self.info_hash,
                    peer_id=self.peer_id,
                    port=self.port,
                    uploaded=self.peer_manager.uploaded,
                    downloaded=self.peer_manager.downloaded,
                    left=self.peer_manager.left,
                    ip=self.ip,
                    timeout=self.udp_tracker_timeout,
                    retry_backoff_factor=self.udp_tracker_retry_backoff_factor,
                    max_retries=self.udp_tracker_max_retries
                )
            except UDPTrackerError as exc:
                logger.error(exc)
                continue

            await self._response_queue.put((tracker, response))

    def add_tracker(self, tracker: TrackerClient, interval: int | None = None) -> None:
        if isinstance(tracker, HTTPTrackerClient):
            announce_coro = self._announce_http_tracker(tracker, interval)
        elif isinstance(tracker, UDPTrackerClient):
            announce_coro = self._announce_udp_tracker(tracker, interval)
        else:
            raise TypeError(f"Unsupported tracker client: {tracker}")

        self._announce_tasks[tracker] = asyncio.create_task(announce_coro)

    def add_trackers(self, trackers: Sequence[TrackerClient], interval: int | None = None) -> None:
        for tracker in trackers:
            self.add_tracker(tracker, interval)

    async def remove_tracker(self, tracker: TrackerClient) -> None:
        try:
            task = self._announce_tasks[tracker]
        except KeyError:
            raise KeyError(f"Tracker client not found: {tracker}")

        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        del self._announce_tasks[tracker]

    async def get_response(self) -> tuple[TrackerClient, TrackerResponse]:
        return await self._response_queue.get()

    async def close(self) -> None:
        for tracker in self._announce_tasks:
            await self.remove_tracker(tracker)

        while not self._response_queue.empty():
            with suppress(asyncio.QueueEmpty):
                self._response_queue.get_nowait()