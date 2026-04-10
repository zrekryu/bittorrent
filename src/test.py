import asyncio
import logging

from bittorrent.metadata.torrent import Torrent
from bittorrent.peers import PeerManager
from bittorrent.trackers import MultiTrackerAnnouncer, PeriodicTrackerAnnouncer
from bittorrent.utils import generate_peer_id

# Create a logger for your bittorrent package
bittorrent_logger = logging.getLogger("bittorrent")

# Set logging level and format for this specific logger
bittorrent_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Add the handler to the logger
bittorrent_logger.addHandler(console_handler)


async def main() -> None:
    torrent = await Torrent.from_path("1.torrent")
    assert torrent.announce_list is not None
    peer_id = generate_peer_id()
    multi_tracker_announcer = MultiTrackerAnnouncer(
        announce_list=torrent.announce_list,
        info_hash=torrent.info_hash,
        peer_id=peer_id,
        port=6681,
        uploaded=0,
        downloaded=0,
        left=torrent.total_length,
        announce_tier_urls_parallel=True,
    )
    tracker, response = await multi_tracker_announcer.announce()
    print(tracker)
    print(response)

    peer_manager = PeerManager()
    peer_manager.uploaded = 0
    peer_manager.downloaded = 0
    peer_manager.left = torrent.total_length

    periodic_tracker_announcer = PeriodicTrackerAnnouncer(
        info_hash=torrent.info_hash,
        peer_id=peer_id,
        port=6681,
        peer_manager=peer_manager,
        interval=5
    )
    periodic_tracker_announcer.add_tracker(tracker)
    print("Got:", await periodic_tracker_announcer._response_queue.get())


asyncio.run(main())
