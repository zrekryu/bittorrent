import asyncio
import logging
from typing import Self

from ..exceptions import PeerError

from ..protocol.peer import Peer
from ..protocol.swarm import Swarm

from .piece import Piece
from .block import Block
from .piece_manager import PieceManager

logger: logging.Logger = logging.getLogger(__name__)

class PieceRequester:
    def __init__(
        self: Self,
        piece_manager: PieceManager,
        swarm: Swarm,
        block_receive_timeout: int
        ) -> None:
        self.piece_manager = piece_manager
        self.swarm = swarm
        self.block_receive_timeout = block_receive_timeout
    
    async def request_block(self: Self, piece: Piece, block: Block) -> list[Peer | tuple[Peer, PeerError]]:
        peers = self.swarm.get_peers(
            unchoked=True,
            can_accept_more_incoming_block_requests=True
            has_pieces=piece.index
            )
        tasks = (
            asyncio.create_task(self.__request_block_from_peer(piece, block, peer))
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
        
        self.add_block_request(piece, block, peer)
    
    async def set_block_receive_timeout(self: Self, piece: Piece, block: Block, peer: Peer) -> None:
        try:
            await asyncio.wait_for(event.wait(), timeout=self.block_receive_timeout)
        except asyncio.TimeoutError:
            await self.on_block_receive_timeout(piece, block, peer)
    
    async def on_block_receive_timeout()


(Piece, Block) -> peers | event
