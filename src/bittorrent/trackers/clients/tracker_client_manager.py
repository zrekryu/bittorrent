import asyncio
import logging
from typing import Final

from bittorrent.exceptions import HTTPTrackerError, UDPTrackerError

from .http import HTTPTrackerClient
from .http.responses import HTTPTrackerAnnounceResponse
from .udp import UDPTrackerClient
from .udp.responses import UDPTrackerAnnounceResponse

logger = logging.getLogger(__name__)

type TrackerClient = HTTPTrackerClient | UDPTrackerClient
type TrackerResponse = HTTPTrackerAnnounceResponse | UDPTrackerAnnounceResponse


class TrackerClientManager:
    DEFAULT_INTERVAL: Final[int] = 120

    def __init__(
        self,
        announce_list: list[list[str]],
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        interval: int = DEFAULT_INTERVAL,
        follow_response_interval: bool = True,
    ) -> None:
        self.announce_list = announce_list

        self.__info_hash = info_hash
        self.__peer_id = peer_id
        self.__port = port

        self.interval = interval
        self.follow_response_interval = follow_response_interval

        self._announce_tasks: dict[TrackerClient, asyncio.Task[None]] = {}
        self._announce_response_queue: asyncio.Queue[TrackerResponse] = asyncio.Queue()

    async def _announce_tracker(
        self,
        tracker: TrackerClient,
        interval: int | None = None,
        follow_response_interval: bool = True,
    ) -> None:
        interval = interval or self.interval

        while True:
            await asyncio.sleep(interval)

            try:
                response: TrackerResponse = await tracker.announce(
                    info_hash=self.__info_hash, peer_id=self.__peer_id, port=self.__port
                )  # type: ignore
            except (HTTPTrackerError, UDPTrackerError) as exc:
                logger.error("Interval tracker announce failed: %s", str(exc))
                continue

            logger.debug("Interval tracker announce response: %s", str(response))

            if follow_response_interval and response.interval > 0:
                interval = response.interval

            await self._announce_response_queue.put(response)

    def add_tracker(
        self,
        tracker: TrackerClient,
        interval: int | None = None,
        follow_response_interval: bool = True,
    ) -> None:
        self._announce_tasks[tracker] = asyncio.create_task(
            self._announce_tracker(tracker, interval, follow_response_interval)
        )

    async def remove_tracker(self, tracker: TrackerClient) -> None:
        task: asyncio.Task[None] | None = self._announce_tasks.get(tracker)
        if task is None:
            raise ValueError(f"Tracker not found: {tracker}")

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            del self._announce_tasks[tracker]

    async def get_response(self) -> TrackerResponse:
        return await self._announce_response_queue.get()
