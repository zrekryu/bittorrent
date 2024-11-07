from bisect import insort
from collections import Counter, deque
import hashlib
import math
from typing import Generator, Self

from ..enums import BlockStatus
from ..protocol.messages import BitFieldMessage

from .piece import Piece
from .block import Block

class PieceManager:
    def __init__(
        self: Self,
        pieces: list[Piece],
        pieces_hash: bytes,
        block_size: int = Block.BLOCK_SIZE,
        sort_by_rarity: bool = True
        ) -> None:
        self.pieces = pieces
        self.pieces_hash = pieces_hash
        self.block_size = block_size
        self.sort_by_rarity = sort_by_rarity
        
        self.pieces_availability_counter: Counter[int, int] = Counter({piece.index: 0 for piece in self.pieces})
        
        self.missing_blocks: list[tuple[Piece, Block]] = self.get_missing_blocks_sorted_by_rarity() if self.sort_by_rarity else list(self.get_missing_blocks())
        self.requested_blocks: list[tuple[Piece, Block]] = list(self.get_requested_blocks())
        
        self.bitfield: BitFieldMessage = self.create_bitfield_from_pieces()
    
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
            piece: Piece = Piece(index=piece_index, is_last=is_last_piece)
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
    
    def create_bitfield_from_pieces(self: Self) -> BitFieldMessage:
        return BitFieldMessage.from_pieces_availability(
            total_pieces=len(self.pieces),
            pieces_availability=(piece.all_blocks_available for piece in self.pieces)
            )
    
    def get_missing_blocks(self: Self) -> Generator[tuple[Piece, Block], None, None]:
        return ((piece, block) for piece in self.pieces for block in piece.get_missing_blocks())
    
    def get_missing_blocks_sorted_by_rarity(self: Self) -> list[tuple[Piece, Block]]:
        pieces_blocks: list[tuple[Piece, Block]] = [(piece, block) for piece in self.pieces for block in piece.get_missing_blocks()]
        pieces_blocks.sort(key=lambda piece_block: self.pieces_availability_counter[piece_block[0]])
        return pieces_blocks
    
    def get_requested_blocks(self: Self) -> Generator[tuple[Piece, Block], None, None]:
        return ((piece, block) for piece in self.pieces for block in piece.get_requested_blocks())
    
    def has_piece(self: Self, index: int) -> bool:
        return index in self.pieces
    
    def get_piece(self: Self, index: int) -> Piece:
        try:
            return self.pieces[index]
        except IndexError:
            raise IndexError(f"Piece not found: {index}")
    
    def get_block(self: Self, index: int, begin: int) -> Block:
        return self.get_piece(index).get_block(begin)
    
    def get_block_length(self: Self, index: int, begin: int) -> int:
        return self.get_block(index, begin).length
    
    def get_block_status(self: Self, index: int, begin: int) -> BlockStatus:
        return self.get_block(index, begin).status
    
    @property
    def all_pieces_available(self: Self) -> bool:
        return all(piece.all_blocks_available for piece in self.pieces)
    
    def has_missing_block(self: Self, piece: Piece, block: Block) -> bool:
        return (piece, block) in self.missing_blocks
    
    def has_requested_block(self: Self, piece: Piece, block: Block) -> bool:
        return (piece, block) in self.requested_blocks
    
    def add_missing_block(self: Self, piece: Piece, block: Block, skip_sort_by_rarity: bool = False) -> None:
        if (piece, block) in self.missing_blocks:
            raise ValueError(f"Piece ({piece.index}) and Block ({block.begin}) already exists in missing blocks")
        
        if self.sort_by_rarity and not skip_sort_by_rarity:
            self.add_and_sort_missing_block(piece, block)
        else:
            self.missing_blocks.append((piece, block))
    
    def add_and_sort_missing_block(self: Self, piece: Piece, block: Block) -> None:
        insort(self.missing_blocks, (piece, block), key=lambda piece_block: self.pieces_availability_counter[piece_block[0]])
    
    def remove_missing_block(self: Self, piece: Piece, block: Block) -> None:
        try:
            self.missing_blocks.remove((piece, block))
        except ValueError:
            raise ValueError(f"Piece ({piece.index}) and Block ({block.begin}) not found in missing blocks")
    
    def add_requested_block(self: Self, piece: Piece, block: Block) -> None:
        if (piece, block) in self.requested_blocks:
            raise ValueError(f"Piece ({piece.index}) and Block ({block.begin}) already exists in requested blocks")
        
        self.requested_blocks.append((piece, block))
    
    def remove_requested_block(self: Self, piece: Piece, block: Block) -> None:
        try:
            self.requested_blocks.remove((piece, block))
        except:
            raise ValueError(f"Piece ({piece.index}) and Block ({block.begin}) not found in requested blocks")
    
    def verify_piece(self: Self, index: int, piece: bytes) -> bool:
        piece_hash_begin: int = index * 20
        piece_hash_end: int = piece_hash_begin + 20
        computed_piece_hash: bytes = hashlib.sha1(piece).digest()
        return self.pieces_hash[piece_hash_begin:piece_hash_end] == computed_piece_hash
    
    def calc_pieces_availability(self: Self, bitfields: list[BitFieldMessage]) -> dict[int, int]:
        return {
            piece.index: sum(1 for bitfield in bitfields if bitfield.has_piece(piece.index))
            for piece in self.pieces
        }
    
    def update_piece_availability_count(self: Self, index: int, count: int = 1) -> None:
        self.pieces_availability_counter.update({index: count})
    
    def increment_piece_availability_count(self: Self, index: int, count: int = 1) -> None:
        if count < 0:
            raise ValueError(f"Negative count is not allowed: {count}")
        
        self.pieces_availability_counter[index] += count
    
    def decrement_piece_availability_count(self: Self, index: int, count: int = -1) -> None:
        if count > 0:
            raise ValueError(f"Positive count is not allowed: {count}")
        
        self.pieces_availability_counter[index] -= count
    
    def update_pieces_availability_counter_with_bitfield(self: Self, bitfield: BitFieldMessage) -> None:
        self.pieces_availability_counter.update({index: 1 for index in bitfield.iter_pieces(available=True)})