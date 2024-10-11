from typing import Self

from ..enums import BlockStatus

class Block:
    BLOCK_SIZE: int = 2**14  # 16 KiB.
    
    def __init__(self: Self, begin: int, length: int, status: BlockStatus) -> None:
        self.begin = begin
        self.length = length
        self.status = status
    
    @property
    def is_available(self: Self) -> bool:
        return self.status is BlockStatus.AVAILABLE
    
    @property
    def is_missing(self: Self) -> bool:
        return self.status is BlockStatus.MISSING
    
    @property
    def is_requested(self: Self) -> bool:
        return self.status is BlockStatus.REQUESTED
    
    def __repr__(self: Self) -> str:
        return f"Block(begin={self.begin}, length={self.length}, status={self.status})"