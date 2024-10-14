from collections import Counter
import hashlib
import math
from typing import Self

from ..enums import BlockStatus
from ..protocol.peer import Peer
from ..protocol.messages import BitField

from .piece import Piece
from .block import Block

class PieceManager:
    def __init__(
        self: Self,
        pieces: list[Piece],
        pieces_hash: bytes,
        block_size: int = Block.BLOCK_SIZE
        ) -> None:
        self.pieces = pieces
        self.pieces_hash = pieces_hash
        self.block_size = block_size
        
        self.missing_blocks: list[tuple[int, int]] = self.get_missing_blocks()
        self.requested_blocks: list[tuple[int, int]] = self.get_requested_blocks()
        
        self.pieces_availability_counter: Counter = Counter()
        
        self.bitfield: BitField = self.create_bitfield_from_pieces()
    
    @classmethod
    def create_pieces(
        cls: type[Self],
        piece_length: int,
        last_piece_length: int,
        total_pieces: int,
        last_piece_index: int,
        available: bool,
        block_size: int = Block.BLOCK_SIZE
        ) -> list[Piece]:
        blocks_per_piece: int = piece_length // block_size
        
        pieces: list[Piece] = []
        for piece_index in range(total_pieces):
            is_last_piece: bool = (piece_index == last_piece_index)
            piece: Piece = Piece(index=piece_index, is_last_piece=is_last_piece)
            block_status: BlockStatus = BlockStatus.AVAILABLE if available else BlockStatus.MISSING
            
            # Last piece, which may be smaller than the piece length.
            if is_last_piece and last_piece_length > 0:
                blocks_in_last_piece: int = math.ceil(last_piece_length / block_size)
                blocks: list[Block] = [
                    Block(
                        begin=i * block_size,
                        length=last_piece_length % block_size if i == (blocks_in_last_piece - 1) else block_size,
                        status=block_status
                        ) for i in range(blocks_in_last_piece)
                    ]
                piece.add_blocks(blocks)
            else:
                blocks = [
                    Block(begin=i * block_size, length=block_size, status=block_status)
                    for i in range(blocks_per_piece)
                    ]
                piece.add_blocks(blocks)
            
            pieces.append(piece)
        
        return pieces
    
    def create_bitfield_from_pieces(self: Self) -> BitField:
        return BitField.from_pieces_availability(
            total_pieces=len(self.pieces),
            pieces_availability=(piece.all_blocks_available for piece in self.pieces)
            )
    
    def get_missing_blocks(self: Self) -> list[tuple[int, int]]:
        return [(piece.index, block.begin) for piece in self.pieces for block in piece.get_missing_blocks()]
    
    def get_requested_blocks(self: Self) -> list[tuple[int, int]]:
        return [(piece.index, block.begin) for piece in self.pieces for block in piece.get_requested_blocks()]
    
    def has_piece(self: Self, index: int) -> bool:
        return index in self.pieces
    
    def get_piece(self: Self, index: int) -> Piece:
        try:
            return self.pieces[index]
        except IndexError:
            raise IndexError(f"Piece not found: {index}")
    
    def are_all_blocks_available(self: Self, index: int) -> bool:
        return self.get_piece(index).all_blocks_available
    
    def get_piece_data(self: Self, index: int) -> bytes:
        return self.get_piece(index).get_blocks_data()
    
    def clear_piece_data(self: Self, index: int) -> None:
        self.get_piece(index).clear_blocks_data()
    
    def get_block(self: Self, index: int, begin: int) -> Block:
        return self.get_piece(index).get_block(begin)
    
    def get_block_length(self: Self, index: int, begin: int) -> int:
        return self.get_block(index, begin).length
    
    def get_block_status(self: Self, index: int, begin: int) -> BlockStatus:
        return self.get_block(index, begin).status
    
    def set_block_status_as_missing(self: Self, index: int, begin: int) -> None:
        self.get_block(index, begin).set_status_as_missing()
    
    def set_block_status_as_requested(self: Self, index: int, begin: int) -> None:
        self.get_block(index, begin).set_status_as_requested()
    
    def set_block_status_as_available(self: Self, index: int, begin: int) -> None:
        self.get_block(index, begin).set_status_as_available()
    
    def set_block_data(self: Self, index: int, begin: int, data: bytes) -> None:
        self.get_block(index, begin).set_data(data)
    
    @property
    def all_pieces_available(self: Self) -> bool:
        return all(piece.all_blocks_available for piece in self.pieces)
    
    def sort_missing_blocks_by_rarity(self: Self) -> None:
        self.missing_blocks.sort(key=lambda item: self.pieces_availability_counter[item[0]])
    
    def add_missing_block(self: Self, index: int, begin: int) -> None:
        if (index, begin) in self.missing_blocks:
            raise KeyError(f"Block with piece index ({index}) and begin ({begin}) already exists in missing blocks")
        
        self.missing_blocks.append((index, begin))
    
    def remove_missing_block(self: Self, index: int, begin: int) -> None:
        try:
            self.missing_blocks.remove((index, begin))
        except IndexError:
            raise IndexError(f"Block with piece index ({index}) and begin ({begin}) not found in missing blocks")
    
    def add_requested_block(self: Self, index: int, begin: int) -> None:
        if (index, begin) in self.requested_blocks:
            raise IndexError(f"Block with piece index ({index}) and begin ({begin}) already exists in requested blocks")
        
        self.requested_blocks.append((index, begin))
    
    def remove_requested_block(self: Self, index: int, begin: int) -> None:
        if (index, begin) not in self.requested_blocks:
            raise IndexError(f"Block with piece index ({index}) and begin ({begin}) not found in requested blocks")
        
        self.requested_blocks.remove((index, begin))
    
    def verify_piece(self: Self, index: int, piece: bytes) -> bool:
        piece_hash_begin: int = index * 20
        piece_hash_end: int = piece_hash_begin + 20
        computed_piece_hash: bytes = hashlib.sha1(piece).digest()
        return self.pieces_hash[piece_hash_begin:piece_hash_end] == computed_piece_hash
    
    def calc_pieces_availability(self: Self, peers: list[Peer]) -> dict[int, int]:
        return {
            piece.index: sum(1 for peer in peers if peer.bitfield.has_piece(piece.index))
            for piece in self.pieces
        }
    
    def update_pieces_availability_counter_with_bitfield(self: Self, bitfield: BitField) -> None:
        self.pieces_availability_counter.update({index: 1 for index in bitfield.iter_pieces(available=True)})
    
    def update_pieces_availability_counter(self: Self, peers: list[Peer]) -> None:
        self.pieces_availability_counter.update(self.calc_pieces_availability(peers))