import asyncio
import logging
from collections.abc import Sequence

from bittorrent.enums import HTTPTrackerEvent, UDPTrackerEvent
from bittorrent.exceptions import TrackerError
from bittorrent.types import TrackerClient, TrackerResponse

from .clients.http import HTTPTrackerClient
from .clients.http.responses import HTTPTrackerAnnounceResponse
from .clients.udp import UDPTrackerClient
from .torrent_announce_list import TorrentAnnounceList
from .torrent_announce_list_tier import TorrentAnnounceListTier

logger = logging.getLogger(__name__)


class MultiTrackerAnnouncer:
    def __init__(
        self,
        announce_list: Sequence[Sequence[str]] | TorrentAnnounceList,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        uploaded: int,
        downloaded: int,
        left: int,
        compact: bool = True,
        ipv6: bool = False,
        ip: str | None = None,
        http_tracker_timeout: int = HTTPTrackerClient.TIMEOUT,
        udp_tracker_timeout: int = UDPTrackerClient.TIMEOUT,
        udp_tracker_retry_backoff_factor: int = UDPTrackerClient.RETRY_BACKOFF_FACTOR,
        udp_tracker_max_retries: int = UDPTrackerClient.MAX_RETRIES,
        announce_tier_urls_parallel: bool = False,
    ) -> None:
        self.announce_list: TorrentAnnounceList = (
            TorrentAnnounceList.from_list(announce_list)
            if not isinstance(announce_list, TorrentAnnounceList)
            else announce_list
        )

        self.info_hash = info_hash
        self.peer_id = peer_id
        self.port = port

        self.uploaded = uploaded
        self.downloaded = downloaded
        self.left = left

        self.compact = compact
        self.ipv6 = ipv6
        self.ip = ip

        self.http_tracker_timeout = http_tracker_timeout

        self.udp_tracker_timeout = udp_tracker_timeout
        self.udp_tracker_retry_backoff_factor = udp_tracker_retry_backoff_factor
        self.udp_tracker_max_retries = udp_tracker_max_retries

        self.announce_tier_urls_parallel = announce_tier_urls_parallel

    async def announce_http_tracker(
        self, announce_url: str
    ) -> tuple[HTTPTrackerClient, HTTPTrackerAnnounceResponse]:
        tracker = HTTPTrackerClient(
            announce_url=announce_url, timeout=self.http_tracker_timeout
        )

        response = await tracker.announce(
            info_hash=self.info_hash,
            peer_id=self.peer_id,
            port=self.port,
            uploaded=self.uploaded,
            downloaded=self.downloaded,
            left=self.left,
            compact=self.compact,
            event=HTTPTrackerEvent.STARTED,
            ipv6=self.ipv6,
            ip=self.ip,
        )

        return (tracker, response)

    async def announce_udp_tracker(
        self, announce_url: str
    ) -> tuple[TrackerClient, TrackerResponse]:
        tracker = UDPTrackerClient(
            announce_url=announce_url,
            timeout=self.udp_tracker_timeout,
            retry_backoff_factor=self.udp_tracker_retry_backoff_factor,
            max_retries=self.udp_tracker_max_retries,
        )

        await tracker.connect()

        response = await tracker.announce(
            info_hash=self.info_hash,
            peer_id=self.peer_id,
            port=self.port,
            uploaded=self.uploaded,
            downloaded=self.downloaded,
            left=self.left,
            event=UDPTrackerEvent.STARTED,
            ip=self.ip,
        )

        return (tracker, response)

    async def announce_tracker(
        self, announce_url: str
    ) -> tuple[TrackerClient, TrackerResponse]:
        if announce_url.startswith(("http://", "https://")):
            return await self.announce_http_tracker(announce_url)
        elif announce_url.startswith("udp://"):
            return await self.announce_udp_tracker(announce_url)
        else:
            raise TrackerError(f"Unsupported tracker announce URL: {announce_url}")

    async def announce_tier_sequential(
        self, tier: TorrentAnnounceListTier
    ) -> tuple[TrackerClient, TrackerResponse]:
        for url in tier:
            try:
                tracker, response = await self.announce_tracker(url)
            except TrackerError as exc:
                logger.error(exc)
                continue

            tier.promote(url)
            return tracker, response
        else:
            raise TrackerError("No tracker suceeded in this tier")

    async def announce_tier_parallel(
        self, tier: TorrentAnnounceListTier
    ) -> tuple[TrackerClient, TrackerResponse]:
        tasks: list[asyncio.Task[tuple[TrackerClient, TrackerResponse]]] = [
            asyncio.create_task(self.announce_tracker(url)) for url in tier.urls
        ]
        try:
            async for task in asyncio.as_completed(tasks):
                try:
                    tracker, response = await task
                except TrackerError as exc:
                    logger.error(exc)
                    continue

                tier.promote(tracker.announce_url)
                return tracker, response
            else:
                raise TrackerError("No tracker suceeded in this tier")
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def announce(self) -> tuple[TrackerClient, TrackerResponse]:
        for tier in self.announce_list.tiers:
            if self.announce_tier_urls_parallel:
                try:
                    return await self.announce_tier_parallel(tier)
                except TrackerError as exc:
                    logger.error(exc)
                    continue
            else:
                try:
                    return await self.announce_tier_sequential(tier)
                except TrackerError as exc:
                    logger.error(exc)
                    continue
        else:
            raise TrackerError("No tracker is working")
