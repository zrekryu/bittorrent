import asyncio
import logging
from typing import Any, Callable, Self

from ..exceptions import PeerError
from ..enums import BlockStatus

from ..torrent import Torrent

from ..protocol.handshake import Handshake
from ..protocol.peer import Peer
from ..protocol.swarm import Swarm
from ..protocol.messages import (
    Message,
    KeepAlive,
    Choke, Unchoke,
    Have, BitField,
    Interested, NotInterested,
    Request, Piece, Cancel,
    Port
    )

from .piece_manager import PieceManager
from .file_handler import FileHandler

logger: logging.Logger = logging.getLogger(__name__)

class Leecher:
    MAX_BLOCK_REQUESTS_TO_PEERS: int = 10
    MAX_BLOCK_REQUESTS_PER_PEER: int = 10
    PEER_BLOCK_DELIVERY_TIMEOUT: int = 30
    
    def __init__(
        self: Self,
        download_path: str,
        torrent: Torrent,
        handshake: Handshake,
        piece_manager: PieceManager,
        swarm: Swarm,
        max_block_requests_to_peers: int = MAX_BLOCK_REQUESTS_TO_PEERS,
        max_block_requests_per_peer: int = MAX_BLOCK_REQUESTS_PER_PEER,
        peer_block_delivery_timeout: int = PEER_BLOCK_DELIVERY_TIMEOUT
        ) -> None:
        self.download_path = download_path
        self.torrent = torrent
        self.handshake = handshake
        self.piece_manager = piece_manager
        self.swarm = swarm
        self.max_block_requests_to_peers = max_block_requests_to_peers
        self.max_block_requests_per_peer = max_block_requests_per_peer
        self.peer_block_delivery_timeout = peer_block_delivery_timeout
        
        self.__peer_queue: asyncio.Queue = asyncio.Queue()
        self.__peer_message_queue: asyncio.Queue = asyncio.Queue()
        
        self.__on_peer_connected_task: asyncio.Task | None = None
        self.__on_peer_message_task: asyncio.Task | None = None
        
        self.file_handler: FileHandler = FileHandler(
            name=self.torrent.name,
            piece_length=self.torrent.piece_length,
            path=self.download_path,
            files=self.torrent.info[b"info"][b"files"] if self.torrent.has_multiple_files else None
            )
    
    def start(self: Self) -> None:
        if self.piece_manager.all_pieces_available:
            raise RuntimeError("All pieces are already available")
        
        self.swarm.add_peer_queue(self.__peer_queue)
        self.swarm.add_peer_message_queue(self.__peer_message_queue)
        
        self.__on_peer_connected_task = asyncio.create_task(self.__on_peer_connected())
        self.__on_peer_message_task = asyncio.create_task(self.__on_peer_message())
    
    async def __on_peer_connected(self: Self) -> None:
        while True:
            peer: Peer = await self.__peer_queue.get()
            await self.__handle_peer_connected(peer)
    
    async def __handle_peer_connected(self: Self, peer: Peer) -> None:
        try:
            await peer.do_handshake(self.handshake)
        except PeerError:
            await self.swarm.disconnect_peer(peer)
            return
        
        self.swarm.start_peer_message_reading(peer)
        self.swarm.start_peer_periodic_keep_alive(peer)
        self.swarm.start_peer_inactivity_monitor(peer)
        
        await peer.send_message(Interested())
    
    async def __on_peer_message(self: Self) -> None:
        while True:
            peer: Peer
            message: Message
            peer, message = await self.__peer_message_queue.get()
            
            await self.__handle_message(peer, message)
    
    async def __handle_message(self: Self, peer: Peer, message: Message) -> None:
        match message:
            case KeepAlive() | Choke() | Unchoke() | Interested() | NotInterested() | Have() | BitField() | Request() | Cancel() | Port():
                pass
            case Piece():
                await self.__handle_piece_message(peer, message)
            case _:
                logger.error(f"[{peer.addr_str}] - Unhandled message: {message}.")
    
    async def __handle_piece_message(self: Self, peer: Peer, piece_msg: Piece) -> None:
        index: int = piece_msg.index
        begin: int = piece_msg.begin
        length: int = piece_msg.length
        logger.debug(f"[{peer.addr_str}] - Received piece message: {index}:{begin}:{length}.")
        
        if (piece_msg.index, piece_msg.begin) not in peer.requested_block_requests:
            logger.debug(f"[{peer.addr_str}] - Received unrequested piece: {index}:{begin}.")
        
        self.piece_manager.set_block_status(index, begin, BlockStatus.AVAILABLE)
        
        if self.piece_manager.get_piece(index).all_blocks_available:
            if not self.piece_manager.verify_piece(index, piece_msg.piece):
                logger.error(f"[{peer.addr_str}] - Received piece that did not match hash: {index}:{begin}.")
                return
        
        try:
            await self.file_handler.write_piece(index, begin, piece_msg.data)
        except Exception as exc:
            logger.error(f"Failed to write piece '")
        logger.info(f"[{peer.addr_str}] - Downloaded piece '{index}'.")
    
    async def stop(self: Self) -> None:
        self.swarm.remove_peer_queue(self.__peer_queue)
        self.swarm.remove_peer_message_queue(self.__peer_message_queue)
        
        self.__on_peer_connected_task.cancel()
        self.__on_peer_message_task.cancel()
        await asyncio.wait({
            self.__on_peer_connected_task,
            self.__on_peer_message_task
        })
        
        self.__on_peer_connected_task = None
        self.__on_peer_message_task = None