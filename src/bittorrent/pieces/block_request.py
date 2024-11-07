from typing import Self

from ..protocol.peer import Peer

from .piece import Piece
from .block import Block

class BlockRequest:
    def __init__(self: Self, piece: Piece, block: Block) -> None:
        self.piece = piece
        self.block = block
        
        self.peers: list[Peer] = []
        self.block_received_event: asyncio.Event = asyncio.Event()
    
    def add_peer(self: Self, peer: Peer) -> None:
        if peer in self.peers:
            raise ValueError(f"Peer already exists: {peer}")
        
        self.peers.append(peer)
    
    def add_peers(self: Self, peers: list[Peer]) -> None:
        duplicate_peers: list[Peer] = [peer for peer in peers if peer in self.peers]
        if duplicate_peers:
            raise ValueError(f"Duplicate peers are not allowed: {duplicate_peers}")
        
        self.peers.extend(peers)
    
    def set_block_received(self: Self) -> None:
        if self.block_received_event.is_set():
            raise ValueError("Block was already received")
        
        self.block_received_event.set()
    
    def reset(self: Self) -> None:
        self.peers.clear()
        self.block_received_event.clear()