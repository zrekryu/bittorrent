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

from .protocol.messages import BitField
from .protocol.handshake import Handshake
from .protocol.peer import Peer
from .protocol.swarm import Swarm

from .pieces.piece_manager import PieceManager
from .pieces.file_handler import FileHandler
from .pieces.leecher import Leecher

class TorrentClient:
    def __init__(
        self: Self,
        torrent_settings: TorrentSettings,
        torrent_file_path: str,
        torrent: Torrent
        ) -> None:
        self.torrent_settings = torrent_settings
        self.torrent_file_path = torrent_file_path
        self.torrent = torrent
        
        self.peer_id = self.torrent_settings.get_var("peer_id")
        self.port = self.torrent_settings.get_var("port")
        
        self.debug: bool | None = self.torrent_settings.get_var("debug")
        self.logger: logging.Logger | None = self.__initialize_logger(self.debug)
        
        self.info_hash = generate_info_hash(self.torrent.info)
        
        self.handshake: Handshake = Handshake(
            pstrlen=len(ProtocolString.BITTORRENT_PROTOCOL_V1.value),
            pstr=ProtocolString.BITTORRENT_PROTOCOL_V1.value,
            reserved=bytes(8),
            info_hash=self.info_hash,
            peer_id=self.peer_id
            )
        
        self.multi_tracker_announcer: MultiTrackerAnnouncer | None = None
        self.tracker_peers_info: dict[TrackerHTTP | TrackerUDP, list[tuple[str, int]]] = {}
        
        self.piece_manager: PieceManager | None = None
        self.swarm: Swarm | None = None
        
        self.file_handler: FileHandler | None = None
        
        self.leecher: Leecher | None = None
    
    @classmethod
    async def initialize(cls: type[Self], torrent_file_path: str, torrent_settings: TorrentSettings) -> None:
        if torrent_settings.get_var("peer_id") is None:
            torrent_settings.set_var("peer_id", generate_peer_id())
        
        if torrent_settings.get_var("port") is None:
            torrent_settings.set_var("port", await get_free_bittorrent_port())
        
        return cls(
            torrent_file_path=torrent_file_path,
            torrent=await Torrent.from_file(torrent_file_path),
            torrent_settings=torrent_settings
        )
    
    def __initialize_logger(self: Self, debug: bool) -> logging.Logger:
        logger = logging.getLogger("bittorrent")
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        stream_handler: logging.StreamHandler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] - %(levelname)s - %(name)s - %(message)s", datefmt="%d/%m/%y %H:%M:%S")
        stream_handler.setFormatter(formatter)
        
        logger.addHandler(stream_handler)
        
        logger.info(f"Logger has been initialized. [DEBUG: {debug}]")
        return logger
    
    def __initialize_multi_tracker_announcer(self: Self) -> MultiTrackerAnnouncer:
        return MultiTrackerAnnouncer(
            tiers=decode_announce_list(self.torrent.announce_list),
            desired_successful_trackers=self.torrent_settings.get_var("desired_successful_trackers"),
            info_hash=self.info_hash,
            peer_id=self.peer_id,
            port=self.port,
            uploaded=0,
            downloaded=0,
            left=self.torrent.total_length,
            compact=self.torrent_settings.get_var("compact"),
            no_peer_id=self.torrent_settings.get_var("no_peer_id"),
            ip=self.torrent_settings.get_var("ip"),
            numwant=self.torrent_settings.get_var("numwant"),
            tracker_http_key=self.torrent_settings.get_var("tracker_http_key"),
            tracker_udp_key=self.torrent_settings.get_var("tracker_udp_key"),
            tracker_http_timeout=self.torrent_settings.get_var("tracker_http_timeout"),
            tracker_udp_timeout=self.torrent_settings.get_var("tracker_udp_timeout"),
            tracker_udp_retries=self.torrent_settings.get_var("tracker_udp_retries")
            )
    
    async def __announce_stopped_event_to_trackers(self: Self) -> None:
        tasks: list[asyncio.Task] = []
        for tracker, peers_info in self.tracker_peers_info.items():
            peers = filter(lambda peer: (peer.ip, peer.port) in peers_info, self.swarm.peers)
            uploaded: int = sum(peer.uploaded for peer in peers)
            downloaded: int = sum(peer.downloaded for peer in peers)
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
                        compact=self.torrent_settings.get_var("compact"),
                        no_peer_id=self.torrent_settings.get_var("no_peer_id"),
                        event=TrackerHTTPEvent.STOPPED.value,
                        ip=self.torrent_settings.get_var("ip"),
                        numwant=self.torrent_settings.get_var("numwant"),
                        key=self.torrent_settings.get_var("tracker_http_key")
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
                        compact=self.torrent_settings.get_var("compact"),
                        no_peer_id=self.torrent_settings.get_var("no_peer_id"),
                        event=TrackerUDPEvent.STOPPED.value,
                        ip=self.torrent_settings.get_var("ip"),
                        numwant=self.torrent_settings.get_var("numwant"),
                        key=self.torrent_settings.get_var("tracker_http_key")
                        )
                    ))
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def __initialize_piece_manager(self: Self) -> PieceManager:
        return PieceManager(
            pieces=PieceManager.create_pieces(
                piece_length=self.torrent.piece_length,
                last_piece_length=self.torrent.last_piece_length,
                total_pieces=self.torrent.total_pieces,
                last_piece_index=self.torrent.last_piece_index,
                available=False,
                block_size=self.torrent_settings.get_var("block_size")
            ),
            pieces_hash=self.torrent.info[b"pieces"],
            block_size=self.torrent_settings.get_var("block_size")
            )
    
    def __initialize_swarm(self: Self) -> Swarm:
        return Swarm(
            bitfield=BitField.create_bitfield(
                total_pieces=self.torrent.total_pieces,
                available=False
            ),
            piece_manager=self.piece_manager,
            connect_timeout=self.torrent_settings.get_var("connect_timeout"),
            handshake_timeout=self.torrent_settings.get_var("handshake_timeout"),
            chunk_size=self.torrent_settings.get_var("chunk_size"),
            max_connections=self.torrent_settings.get_var("max_connections"),
            keep_alive_interval=self.torrent_settings.get_var("keep_alive_interval"),
            keep_alive_timeout=self.torrent_settings.get_var("keep_alive_timeout")
            )
    
    def __initialize_file_handler(self: Self) -> FileHandler:
        return FileHandler(
            name=self.torrent.name,
            piece_length=self.torrent.piece_length,
            last_piece_length=self.torrent.last_piece_length,
            last_piece_index=self.torrent.last_piece_index,
            path=self.torrent_settings.get_var("download_path"),
            files=self.torrent.info[b"info"][b"files"] if self.torrent.has_multiple_files else None
            )
    
    def __initialize_leecher(self: Self) -> Leecher:
        return Leecher(
            handshake=self.handshake,
            piece_manager=self.piece_manager,
            swarm=self.swarm,
            file_handler=self.file_handler,
            max_block_requests_per_peer=self.torrent_settings.get_var("max_block_requests_per_peer")
            )
    
    async def __add_peers_info_to_tracker(self: Self, tracker: TrackerHTTP | TrackerUDP, peers: list[Peer]) -> None:
        if tracker not in self.tracker_peers_info:
            self.tracker_peers_info[tracker] = []
        
        self.tracker_peers_info[tracker].extend(peers)
    
    async def start_leeching(self: Self) -> None:
        if not self.torrent.announce and not self.torrent.announce_list:
            self.logger.error("No tracker URI is present in announce and announce_list keys.")
            raise RuntimeError("At least one tracker URI must be present in either announce or announce-list key in the torrent file")
        
        if not self.multi_tracker_announcer:
            self.multi_tracker_announcer = self.__initialize_multi_tracker_announcer()
        
        if not self.piece_manager:
            self.piece_manager = self.__initialize_piece_manager()
        
        if not self.swarm:
            self.swarm = self.__initialize_swarm()
        
        if not self.file_handler:
            self.file_handler = self.__initialize_file_handler()
        
        if not self.leecher:
            self.leecher = self.__initialize_leecher()
        
        self.leecher.start()
        
        trackers_responses: list[tuple[TrackerHTTP, TrackerHTTPAnnounceResponse] | tuple[TrackerUDP, TrackerUDPAnnounceResponse]]
        trackers_responses = await self.multi_tracker_announcer.announce_trackers()
        for tracker, response in trackers_responses:
            peers: list[tuple[str, int]] = decode_compact_peers(response.peers) if isinstance(response.peers, bytes) else response.peers
            await self.__add_peers_info_to_tracker(tracker, peers)
            
            await self.swarm.add_peers(peers)
    
    async def stop_leeching(self: Self) -> None:
        if not self.leecher:
            raise RuntimeError("Leeching is already stopped")
        
        await self.leecher.stop()
    
    async def wait_until_download_complete(self: Self) -> None:
        while not self.piece_manager.all_pieces_available:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
    
    async def close(self: Self) -> None:
        self.multi_tracker_announcer = None
        self.piece_manager = None
        
        if self.leecher:
            await self.leecher.stop()
            self.leecher = None
        
        await self.__announce_stopped_event_to_trackers()
        
        await self.swarm.disconnect_peers()
        self.swarm = None