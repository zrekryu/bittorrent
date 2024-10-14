import asyncio
import logging
from typing import Self

from ..exceptions import PeerError
from ..enums import BlockStatus

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
    ACCEPT_UNREQUESTED_BLOCKS: bool = True
    
    def __init__(
        self: Self,
        handshake: Handshake,
        piece_manager: PieceManager,
        swarm: Swarm,
        file_handler: FileHandler,
        max_block_requests_to_peers: int = MAX_BLOCK_REQUESTS_TO_PEERS,
        max_block_requests_per_peer: int = MAX_BLOCK_REQUESTS_PER_PEER,
        peer_block_delivery_timeout: int = PEER_BLOCK_DELIVERY_TIMEOUT,
        accept_unrequested_blocks: bool = ACCEPT_UNREQUESTED_BLOCKS
        ) -> None:
        self.handshake = handshake
        self.piece_manager = piece_manager
        self.swarm = swarm
        self.file_handler = file_handler
        self.max_block_requests_to_peers = max_block_requests_to_peers
        self.max_block_requests_per_peer = max_block_requests_per_peer
        self.peer_block_delivery_timeout = peer_block_delivery_timeout
        self.accept_unrequested_blocks = accept_unrequested_blocks
        
        self.__peer_queue: asyncio.Queue = asyncio.Queue()
        self.__peer_message_queue: asyncio.Queue = asyncio.Queue()
        
        self.__on_peer_connected_task: asyncio.Task | None = None
        self.__on_peer_message_task: asyncio.Task | None = None
    
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
        
        await peer.send_interested_message()
    
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
        logger.debug(f"[{peer.addr_str}] - Received piece message: {index}:{begin}.")
        
        if (piece_msg.index, piece_msg.begin) not in peer.requested_block_requests:
            logger.debug(f"[{peer.addr_str}] - Received unrequested piece: {index}:{begin}.")
            
            if not self.accept_unrequested_blocks:
                logger.debug(f"[{peer.addr_str}] - Rejected unrequested piece: {index}:{begin}.")
                return
        
        if (index, begin) not in self.piece_manager.missing_blocks:
            logger.debug(f"[{peer.addr_str}] - Received piece is not missing: {index}:{begin}.")
            return
        
        self.piece_manager.set_block_data(index, begin, piece.data)
        self.piece_manager.set_block_status_as_available(index, begin)
        
        if self.piece_manager.are_all_blocks_available(index):
            logger.debug(f"All blocks of piece ({index}) are now available.")
            
            if not self.piece_manager.verify_piece(index, piece_msg.piece):
                logger.error(f"[{peer.addr_str}] - Received piece that did not match hash: {index}:{begin}.")
                return
            
            # Write piece to disk.
            try:
                await self.file_handler.write_piece(index, piece=self.piece_manager.get_piece_data(index))
            except Exception as exc:
                logger.error(f"Failed to write piece ({index}): {exc}.")
            else:
                logger.debug(f"Downloaded piece: {index}.")
                self.piece_manager.clear_piece_data(index)
                self.piece_manager.bitfield.set_piece(index)
                
                # Broadcast have piece.
                await self.swarm.broadcast_have_piece(index)
    
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