import asyncio
import logging
from typing import Self

from .enums import (
    TrackerHTTPEvent,
    TrackerUDPEvent,
    ProtocolString
    )
from .utils import (
    decode_announce_list,
    generate_info_hash,
    generate_peer_id,
    get_free_bittorrent_port,
    decode_compact_peers
)

from .settings import TorrentSettings

from .torrent import Torrent
from .trackers.responses import TrackerHTTPAnnounceResponse, TrackerUDPAnnounceResponse
from .trackers import TrackerHTTP, TrackerUDP, MultiTrackerAnnouncer

from .protocol.messages import BitFieldMessage
from .protocol.handshake import Handshake
from .protocol.peer import Peer
from .protocol.swarm import Swarm

from .pieces.piece_manager import PieceManager
from .pieces.file_handler import FileHandler
from .pieces.leecher import Leecher

class TorrentClient:
    def __init__(
        self: Self,
        file_path: str,
        torrent: Torrent,
        settings: TorrentSettings
        ) -> None:
        self.file_path = file_path
        self.torrent = torrent
        self.settings = settings
        
        self.peer_id = self.settings.get_var("peer_id")
        self.port = self.settings.get_var("port")
        
        self.debug: bool | None = self.settings.get_var("debug")
        self.logger: logging.Logger | None = self.initialize_logger(self.debug)
        
        self.info_hash = generate_info_hash(self.torrent.info)
        
        self.handshake: Handshake = self.create_handshake()
        
        self.multi_tracker_announcer: MultiTrackerAnnouncer | None = None
        self.tracker_peers_info: dict[TrackerHTTP | TrackerUDP, list[tuple[str, int]]] = {}
        
        self.piece_manager: PieceManager | None = None
        self.swarm: Swarm | None = None
        
        self.file_handler: FileHandler | None = None
        
        self.leecher: Leecher | None = None
    
    @classmethod
    async def initialize(cls: type[Self], file_path: str, settings: TorrentSettings) -> None:
        if settings.get_var("peer_id") is None:
            settings.set_var("peer_id", generate_peer_id())
        
        if settings.get_var("port") is None:
            settings.set_var("port", await get_free_bittorrent_port())
        
        return cls(
            file_path=file_path,
            torrent=await Torrent.from_file(file_path),
            settings=settings
        )
    
    def initialize_logger(self: Self, debug: bool) -> logging.Logger:
        logger = logging.getLogger("bittorrent")
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        stream_handler: logging.StreamHandler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] - %(levelname)s - %(name)s - %(message)s", datefmt="%d/%m/%y %H:%M:%S")
        stream_handler.setFormatter(formatter)
        
        logger.addHandler(stream_handler)
        
        logger.info(f"Logger has been initialized. [DEBUG: {debug}]")
        return logger
    
    def create_handshake(self: Self) -> Handshake:
        return Handshake(
            pstrlen=len(ProtocolString.BITTORRENT_PROTOCOL_V1.value),
            pstr=ProtocolString.BITTORRENT_PROTOCOL_V1.value,
            reserved=bytes(8),
            info_hash=self.info_hash,
            peer_id=self.info_hash
            )
    
    def initialize_multi_tracker_announcer(self: Self) -> MultiTrackerAnnouncer:
        return MultiTrackerAnnouncer(
            tiers=decode_announce_list(self.torrent.announce_list),
            desired_successful_trackers=self.settings.get_var("desired_successful_trackers"),
            info_hash=self.info_hash,
            peer_id=self.peer_id,
            port=self.port,
            uploaded=0,
            downloaded=0,
            left=self.torrent.total_length,
            compact=self.settings.get_var("compact"),
            no_peer_id=self.settings.get_var("no_peer_id"),
            ip=self.settings.get_var("ip"),
            numwant=self.settings.get_var("numwant"),
            tracker_http_key=self.settings.get_var("tracker_http_key"),
            tracker_udp_key=self.settings.get_var("tracker_udp_key"),
            tracker_http_timeout=self.settings.get_var("tracker_http_timeout"),
            tracker_udp_timeout=self.settings.get_var("tracker_udp_timeout"),
            tracker_udp_retries=self.settings.get_var("tracker_udp_retries")
            )
    
    async def announce_stopped_event_to_trackers(self: Self) -> None:
        tasks: list[asyncio.Task] = []
        for tracker, peers_info in self.tracker_peers_info.items():
            peers = filter(lambda peer: (peer.host, peer.port) in peers_info, self.swarm.peers)
            uploaded: int = sum(peer.downloaded for peer in peers)
            downloaded: int = sum(peer.uploaded for peer in peers)
            left: int = self.torrent.total_length
            
            if isinstance(tracker, TrackerHTTP):
                tasks.append(asyncio.create_task(
                    tracker.send_announce(
                        info_hash=self.info_hash,
                        peer_id=self.peer_id,
                        port=self.port,
                        uploaded=uploaded,
                        downloaded=downloaded,
                        left=left,
                        compact=self.settings.get_var("compact"),
                        no_peer_id=self.settings.get_var("no_peer_id"),
                        event=TrackerHTTPEvent.STOPPED.value,
                        ip=self.settings.get_var("ip"),
                        numwant=self.settings.get_var("numwant"),
                        key=self.settings.get_var("tracker_http_key")
                        )
                    ))
            elif isinstance(tracker, TrackerUDP):
                tasks.append(asyncio.create_task(
                    tracker.send_announce(
                        info_hash=self.info_hash,
                        peer_id=self.peer_id,
                        port=self.port,
                        uploaded=uploaded,
                        downloaded=downloaded,
                        left=left,
                        compact=self.settings.get_var("compact"),
                        no_peer_id=self.settings.get_var("no_peer_id"),
                        event=TrackerUDPEvent.STOPPED.value,
                        ip=self.settings.get_var("ip"),
                        numwant=self.settings.get_var("numwant"),
                        key=self.settings.get_var("tracker_http_key")
                        )
                    ))
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def initialize_piece_manager(self: Self) -> PieceManager:
        return PieceManager(
            pieces=PieceManager.create_pieces(
                piece_length=self.torrent.piece_length,
                last_piece_length=self.torrent.last_piece_length,
                total_pieces=self.torrent.total_pieces,
                last_piece_index=self.torrent.last_piece_index,
                available=False,
                block_size=self.settings.get_var("block_size")
            ),
            pieces_hash=self.torrent.info[b"pieces"],
            block_size=self.settings.get_var("block_size")
            )
    
    def initialize_swarm(self: Self) -> Swarm:
        return Swarm(
            bitfield=BitFieldMessage.create_bitfield(
                total_pieces=self.torrent.total_pieces,
                available=False
            ),
            piece_manager=self.piece_manager,
            connect_timeout=self.settings.get_var("peer_connect_timeout"),
            handshake_timeout=self.settings.get_var("peer_handshake_timeout"),
            chunk_size=self.settings.get_var("chunk_size"),
            max_connections=self.settings.get_var("max_connections"),
            keep_alive_interval=self.settings.get_var("keep_alive_interval"),
            inactivity_timeout=self.settings.get_var("inactivity_timeout")
            )
    
    def initialize_file_handler(self: Self) -> FileHandler:
        return FileHandler(
            name=self.torrent.name,
            piece_length=self.torrent.piece_length,
            last_piece_length=self.torrent.last_piece_length,
            last_piece_index=self.torrent.last_piece_index,
            path=self.settings.get_var("download_path"),
            files=self.torrent.info[b"files"] if self.torrent.has_multiple_files else None
            )
    
    def initialize_leecher(self: Self) -> Leecher:
        return Leecher(
            handshake=self.handshake,
            piece_manager=self.piece_manager,
            swarm=self.swarm,
            file_handler=self.file_handler,
            max_block_requests_per_peer=self.settings.get_var("max_block_requests_per_peer")
            )
    
    async def add_peer_addresses_to_tracker(self: Self, tracker: TrackerHTTP | TrackerUDP, peers: list[Peer]) -> None:
        if tracker not in self.tracker_peers_info:
            self.tracker_peers_info[tracker] = []
        
        self.tracker_peers_info[tracker].extend(peers)
    
    async def start_leeching(self: Self) -> None:
        if not self.torrent.announce and not self.torrent.announce_list:
            self.logger.error("No tracker URI is present in announce and announce_list keys.")
            raise RuntimeError("At least one tracker URI must be present in either announce or announce-list key in the torrent file")
        
        if not self.multi_tracker_announcer:
            self.multi_tracker_announcer = self.initialize_multi_tracker_announcer()
        
        if not self.piece_manager:
            self.piece_manager = self.initialize_piece_manager()
        
        if not self.swarm:
            self.swarm = self.initialize_swarm()
        
        if not self.file_handler:
            self.file_handler = self.initialize_file_handler()
        
        if not self.leecher:
            self.leecher = self.initialize_leecher()
            self.leecher.start()
        
        trackers_responses: list[tuple[TrackerHTTP, TrackerHTTPAnnounceResponse] | tuple[TrackerUDP, TrackerUDPAnnounceResponse]]
        trackers_responses = await self.multi_tracker_announcer.announce_trackers()
        for tracker, response in trackers_responses:
            peer_addresses: list[PeerAddress] = decode_compact_peers(response.peers) if isinstance(response.peers, bytes) else response.peers
            
            await self.add_peer_addresses_to_tracker(tracker, peer_addresses)
            await self.swarm.add_peers(peer_addresses)
    
    async def stop_leeching(self: Self) -> None:
        if not self.leecher:
            raise RuntimeError("Leeching is already stopped")
        
        await self.leecher.stop()
    
    async def wait_until_download_complete(self: Self) -> None:
        while not self.piece_manager.all_pieces_available:
            await asyncio.sleep(1)
    
    async def close(self: Self) -> None:
        if self.multi_tracker_announcer:
            self.multi_tracker_announcer = None
        
        if self.piece_manager:
            self.piece_manager = None
        
        if self.leecher:
            await self.leecher.stop()
            self.leecher = None
        
        if self.tracker_peers_info:
            await self.announce_stopped_event_to_trackers()
            self.tracker_peers_info.clear()
        
        if self.swarm:
            await self.swarm.close()
            self.swarm = None