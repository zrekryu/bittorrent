import random
from typing import Self

from .block import Block

class Piece:
    def __init__(self: Self, index: int) -> None:
        self.index = index
        
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
    
    def __repr__(self: Self) -> str:
        return f"Piece(index={self.index}, blocks={self.blocks})"