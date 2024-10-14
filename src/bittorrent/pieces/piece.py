import random
from typing import Self

from .block import Block

class Piece:
    def __init__(self: Self, index: int, is_last_piece: bool) -> None:
        self.index = index
        self.is_last_piece = is_last_piece
        
        self.blocks: list[Block] = []
    
    def add_block(self: Self, block: Block) -> None:
        self.blocks.append(block)
    
    def add_blocks(self: Self, blocks: list[Block]) -> None:
        self.blocks.extend(blocks)
    
    def get_block(self: Self, begin: int) -> Block:
        try:
            return self.blocks[begin]
        except IndexError:
            raise IndexError(f"Block not found: {begin}")
    
    @property
    def total_length(self: Self) -> int:
        return sum((block.length for block in self.blocks))
    
    def get_missing_blocks(self: Self) -> list[Block]:
        return [block for block in self.blocks if block.is_missing]
    
    def has_missing_blocks(self: Self) -> bool:
        return any(block.is_missing for block in self.blocks)
    
    def get_random_missing_blocks(self: Self, size: int) -> list[Block] | None:
        blocks: list[Block] = [block for block in self.blocks if block.is_missing]
        
        length: int = len(blocks)
        if size > length:
            size = length
        
        if blocks:
            return random.sample(blocks, k=size)
        else:
            return blocks
    
    @property
    def all_blocks_available(self: Self) -> bool:
        return all(block.is_available for block in self.blocks)
    
    def get_requested_blocks(self: Self) -> list[Block]:
        return [block for block in self.blocks if block.is_requested]
    
    def get_blocks_data(self: Self) -> bytes:
        return b"".join(block.data for block in self.blocks)
    
    def clear_blocks_data(self: Self) -> None:
        for block in self.blocks:
            block.clear_data()
    
    def __repr__(self: Self) -> str:
        return f"Piece(index={self.index}, is_last_piece={self.is_last_piece}, blocks={self.blocks})"