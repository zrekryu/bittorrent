import logging
from collections.abc import Sequence

from bittorrent.peers import PeerManager

from .clients.http import HTTPTrackerClient
from .clients.udp import UDPTrackerClient
from .multi_tracker_announcer import MultiTrackerAnnouncer
from .periodic_tracker_announcer import PeriodicTrackerAnnouncer
from .torrent_announce_list import TorrentAnnounceList

logger = logging.getLogger(__name__)


class TrackerManager:
    def __init__(
        self,
        announce: str,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        peer_manager: PeerManager,
        compact: bool = True,
        ipv6: bool = False,
        ip: str | None = None,
        announce_list: Sequence[Sequence[str]] | TorrentAnnounceList | None = None,
        http_tracker_timeout: int = HTTPTrackerClient.TIMEOUT,
        udp_tracker_timeout: int = UDPTrackerClient.TIMEOUT,
        udp_tracker_retry_backoff_factor: int = UDPTrackerClient.RETRY_BACKOFF_FACTOR,
        udp_tracker_max_retries: int = UDPTrackerClient.MAX_RETRIES,
        announce_tier_urls_parallel: bool = False,
        periodic_tracker_announcement_interval: int = PeriodicTrackerAnnouncer.INTERVAL,
        follow_response_interval: bool = True,
    ) -> None:
        self.announce = announce
        self.announce_list = announce_list

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

        self.announce_tier_urls_parallel = announce_tier_urls_parallel

        self.periodic_tracker_announcement_interval = periodic_tracker_announcement_interval
        self.follow_response_interval = follow_response_interval

        self.multi_tracker_announcer = MultiTrackerAnnouncer(
            announce_list=self.announce_list or [[self.announce]],
            info_hash=self.info_hash,
            peer_id=self.peer_id,
            port=self.port,
            uploaded=self.peer_manager.uploaded,
            downloaded=self.peer_manager.downloaded,
            left=self.peer_manager.left,
            compact=self.compact,
            ipv6=self.ipv6,
            ip=self.ip,
            http_tracker_timeout=self.http_tracker_timeout,
            udp_tracker_timeout=self.udp_tracker_timeout,
            udp_tracker_retry_backoff_factor=self.udp_tracker_retry_backoff_factor,
            udp_tracker_max_retries=self.udp_tracker_max_retries,
            announce_tier_urls_parallel=self.announce_tier_urls_parallel,
        )

        self.periodic_tracker_announcer = PeriodicTrackerAnnouncer(
            info_hash=self.info_hash,
            peer_id=self.peer_id,
            port=self.port,
            peer_manager=self.peer_manager,
            compact=self.compact,
            ipv6=self.ipv6,
            ip=self.ip,
            http_tracker_timeout=self.http_tracker_timeout,
            udp_tracker_timeout=self.udp_tracker_timeout,
            udp_tracker_retry_backoff_factor=self.udp_tracker_retry_backoff_factor,
            udp_tracker_max_retries=self.udp_tracker_max_retries,
            interval=self.periodic_tracker_announcement_interval,
            follow_response_interval=self.follow_response_interval,
        )