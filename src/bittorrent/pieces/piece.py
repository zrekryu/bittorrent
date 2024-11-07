from typing import Self

from .block import Block

class Piece:
    def __init__(self: Self, index: int, is_last: bool) -> None:
        self.index = index
        self.is_last = is_last
        
        self.blocks: list[Block] = []
    
    def add_block(self: Self, block: Block) -> None:
        self.blocks.append(block)
    
    def add_blocks(self: Self, blocks: list[Block]) -> None:
        self.blocks.extend(blocks)
    
    def has_block(self: Self, begin: int) -> bool:
        try:
            next(block for block in self.blocks if block.begin == begin)
            return True
        except StopIteration:
            return False
    
    def get_block(self: Self, begin: int) -> Block:
        try:
            return next(block for block in self.blocks if block.begin == begin)
        except (ValueError, StopIteration):
            raise ValueError(f"Block not found: {begin}") from None
    
    def set_all_blocks_status_as_missing(self: Self) -> None:
        for block in self.blocks:
            block.set_status_as_missing()
    
    def set_all_blocks_status_as_requested(self: Self) -> None:
        for block in self.blocks:
            block.set_status_as_requested()
    
    def set_all_blocks_status_as_available(self: Self) -> None:
        for block in self.blocks:
            block.set_status_as_available()
    
    def get_blocks_data(self: Self) -> bytes:
        return b"".join(block.data for block in self.blocks)
    
    def clear_blocks_data(self: Self) -> None:
        for block in self.blocks:
            block.clear_data()
    
    def has_missing_blocks(self: Self) -> bool:
        return any(block.is_missing for block in self.blocks)
    
    def get_missing_blocks(self: Self) -> list[Block]:
        return [block for block in self.blocks if block.is_missing]
    
    def get_requested_blocks(self: Self) -> list[Block]:
        return [block for block in self.blocks if block.is_requested]
    
    @property
    def all_blocks_available(self: Self) -> bool:
        return all(block.is_available for block in self.blocks)
    
    @property
    def total_length(self: Self) -> int:
        return sum(block.length for block in self.blocks)
    
    def __repr__(self: Self) -> str:
        return f"Piece(index={self.index}, is_last={self.is_last}, blocks={self.blocks})"