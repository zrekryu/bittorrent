import asyncio
import logging
from typing import Self

from ..exceptions import PeerError

from ..protocol.peer import Peer
from ..protocol.swarm import Swarm

from .piece import Piece
from .block import Block
from .piece_manager import PieceManager
from .block_request import BlockRequest

logger: logging.Logger = logging.getLogger(__name__)

class PieceRequester:
    MAX_BLOCK_REQUESTS_TO_PEERS: int = 10
    MAX_BLOCK_REQUESTS_PER_PEER: int = 10
    BLOCK_RECEIVE_TIMEOUT: int = 30
    
    def __init__(
        self: Self,
        piece_manager: PieceManager,
        swarm: Swarm,
        max_block_requests_to_peers: int = MAX_BLOCK_REQUESTS_TO_PEERS,
        max_block_requests_per_peer: int = MAX_BLOCK_REQUESTS_PER_PEER,
        block_receive_timeout: int = BLOCK_RECEIVE_TIMEOUT
        ) -> None:
        self.piece_manager = piece_manager
        self.swarm = swarm
        self.max_block_requests_to_peers = max_block_requests_to_peers
        self.max_block_requests_per_peer = max_block_requests_per_peer
        self.block_receive_timeout = block_receive_timeout
        
        self.block_requests: dict[(Piece, Block), BlockRequest] = {}
        
        self._request_blocks_task: asyncio.Task | None = None
    
    async def ensure_unchoked_peer(self: Self) -> None:
        should_log: bool = True
        while not self.swarm.has_unchoked_peer():
            if should_log:
                logger.info("No unchoked peer(s) are available currently. Waiting for unchoked peer(s)...")
                should_log = False
            
            await asyncio.sleep(1)
    
    async def request_blocks(self: Self) -> None:
        while not self.piece_manager.all_pieces_available:
            await self.ensure_unchoked_peer()
            
            for piece, block in self.piece_manager.missing_blocks:
                await self.request_block(piece, block)
                await asyncio.sleep(0.4)
    
    async def request_block(self: Self, piece: Piece, block: Block) -> list[Peer | tuple[Peer, PeerError]]:
        peers = self.swarm.get_peers(
            unchoked=True,
            can_accept_more_incoming_block_requests=True,
            has_pieces=piece.index
            )
        tasks = (
            asyncio.create_task(self._request_block_from_peer(piece, block, peer))
            for peer in peers
            )
        return await asyncio.gather(*tasks)
    
    async def _request_block_from_peer(self: Self, piece: Piece, block: Block, peer: Peer) -> Peer | tuple[Peer, PeerError]:
        try:
            await self.request_block_from_peer(piece, block, peer)
        except PeerError as exc:
            return (peer, exc)
        
        return peer
    
    async def request_block_from_peer(self: Self, piece: Piece, block: Block, peer: Peer) -> None:
        await peer.send_request_message(piece.index, block.begin, block.length)
        peer.incoming_block_requests.append((piece, block))
        
        self.piece_manager.remove_missing_block(piece, block)
        self.piece_manager.add_requested_block(piece, block)
    
    def start(self: Self) -> None:
        self._request_blocks_task = asyncio.create_task(self.request_blocks())
    
    async def stop(self: Self) -> None:
        self._request_blocks_task.cancel()
        try:
            await self._request_blocks_task
        except asyncio.CancelledError:
            pass
        finally:
            self._request_blocks_task = None