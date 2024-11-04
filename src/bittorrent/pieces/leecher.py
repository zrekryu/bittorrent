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
    KeepAliveMessage,
    ChokeMessage, UnchokeMessage,
    HaveMessage, BitFieldMessage,
    InterestedMessage, NotInterestedMessage,
    RequestMessage, PieceMessage, CancelMessage,
    PortMessage
    )

from .piece import Piece
from .block import Block
from .piece_manager import PieceManager
from .piece_requester import PieceRequester

from .file_handler import FileHandler

logger: logging.Logger = logging.getLogger(__name__)

class Leecher:
    MAX_BLOCK_REQUESTS_TO_PEERS: int = 10
    MAX_BLOCK_REQUESTS_PER_PEER: int = 10
    BLOCK_RECEIVE_TIMEOUT: int = 30
    ACCEPT_UNREQUESTED_BLOCKS: bool = True
    
    def __init__(
        self: Self,
        handshake: Handshake,
        piece_manager: PieceManager,
        swarm: Swarm,
        file_handler: FileHandler,
        max_block_requests_to_peers: int = MAX_BLOCK_REQUESTS_TO_PEERS,
        max_block_requests_per_peer: int = MAX_BLOCK_REQUESTS_PER_PEER,
        block_receive_timeout: int = BLOCK_RECEIVE_TIMEOUT,
        accept_unrequested_blocks: bool = ACCEPT_UNREQUESTED_BLOCKS
        ) -> None:
        self.handshake = handshake
        self.piece_manager = piece_manager
        self.swarm = swarm
        self.file_handler = file_handler
        self.accept_unrequested_blocks = accept_unrequested_blocks
        
        self._peer_queue: asyncio.Queue = asyncio.Queue()
        self._peer_message_queue: asyncio.Queue = asyncio.Queue()
        
        self._on_peer_connected_task: asyncio.Task | None = None
        self._on_peer_message_task: asyncio.Task | None = None
        
        self.piece_requester: PieceRequester = PieceRequester(
            piece_manager=self.piece_manager,
            swarm=self.swarm,
            max_block_requests_per_peer=max_block_requests_per_peer,
            max_block_requests_to_peers=max_block_requests_per_peer,
            block_receive_timeout=block_receive_timeout
            )
    
    def start(self: Self) -> None:
        if self.piece_manager.all_pieces_available:
            raise RuntimeError("All pieces are already available")
        
        self.swarm.add_peer_queue(self._peer_queue)
        self.swarm.add_peer_message_queue(self._peer_message_queue)
        
        self._on_peer_connected_task = asyncio.create_task(self._on_peer_connected())
        self._on_peer_message_task = asyncio.create_task(self.on_peer_message())
        
        self.piece_requester.start()
    
    async def _on_peer_connected(self: Self) -> None:
        while True:
            peer: Peer = await self._peer_queue.get()
            await self.on_peer_connected(peer)
            
            self._peer_queue.task_done()
    
    async def on_peer_connected(self: Self, peer: Peer) -> None:
        try:
            await peer.do_handshake(self.handshake)
        except PeerError:
            await self.swarm.disconnect_peer(peer)
            return
        
        self.swarm.start_peer_message_reading(peer)
        self.swarm.enable_peer_keep_alive_timeout(peer)
        self.swarm.enable_peer_keep_alive_interval(peer)
        
        await peer.send_interested_message()
    
    async def on_peer_message(self: Self) -> None:
        while True:
            peer: Peer
            message: Message
            peer, message = await self._peer_message_queue.get()
            
            await self.handle_message(peer, message)
            
            self._peer_message_queue.task_done()
    
    async def handle_message(self: Self, peer: Peer, message: Message) -> None:
        match message:
            case KeepAliveMessage() | ChokeMessage() | UnchokeMessage() | InterestedMessage() | NotInterestedMessage() | HaveMessage() | BitFieldMessage() | RequestMessage() | CancelMessage() | PortMessage():
                pass
            case PieceMessage():
                await self.handle_piece_message(peer, message)
            case _:
                logger.error(f"[{peer.addr_str}] - Unhandled message: {message}.")
    
    async def handle_piece_message(self: Self, peer: Peer, piece_msg: PieceMessage) -> None:
        index: int = piece_msg.index
        begin: int = piece_msg.begin
        length: int = len(piece_msg.piece)
        
        logger.debug(f"[{peer.addr_str}] - Received piece message: {index}:{begin}.")
        
        if not self.piece_manager.has_requested_block(index, begin):
            logger.debug(f"[{peer.addr_str}] - Received unrequested piece: {index}:{begin}.")
            
            if not self.accept_unrequested_blocks:
                logger.debug(f"[{peer.addr_str}] - Rejected unrequested piece: {index}:{begin}.")
                return
        else:
            self.piece_manager.remove_requested_block(index, begin)
        
        piece: Piece = self.piece_manager.get_piece(index)
        block: Block = piece.get_block(begin)
        
        if length != block.length:
            logger.error(f"[{peer.addr_str}] - Received invalid length of piece ({index}:{begin}): {length} (expected: {block.length}).")
            return
        
        block.set_data(piece_msg.piece)
        block.set_status_as_available()
        
        if piece.all_blocks_available:
            logger.debug(f"All blocks of piece ({index}) are now available.")
            
            if not self.piece_manager.verify_piece(index, piece_msg.piece):
                logger.error(f"[{peer.addr_str}] - Received piece that did not match hash: {index}:{begin}.")
                
                piece.clear_blocks_data()
                piece.set_all_blocks_status_as_missing()
                return
            
            # Write piece to disk.
            try:
                await self.file_handler.write_piece(
                    index=index,
                    piece=piece.get_blocks_data()
                    )
            except Exception as exc:
                logger.error(f"Failed to write piece ({index}): {exc}.")
                raise IOError(f"Failed to write piece ({index}): {exc}")
            
            logger.debug(f"Downloaded piece: {index}.")
            
            piece.clear_blocks_data()
            self.piece_manager.bitfield.set_piece(index)
            
            # Broadcast have piece.
            await self.swarm.broadcast_have_piece(index)
    
    async def stop(self: Self) -> None:
        self.swarm.remove_peer_queue(self._peer_queue)
        self.swarm.remove_peer_message_queue(self._peer_message_queue)
        
        self._on_peer_connected_task.cancel()
        self._on_peer_message_task.cancel()
        await asyncio.gather(
            self._on_peer_connected_task,
            self._on_peer_message_task,
            return_exceptions=True
        )
        
        self._on_peer_connected_task = None
        self._on_peer_message_task = None
        
        await self.piece_requester.stop()