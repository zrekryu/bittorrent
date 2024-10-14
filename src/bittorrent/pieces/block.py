from typing import Self

from ..enums import BlockStatus

class Block:
    BLOCK_SIZE: int = 2**14  # 16 KiB.
    
    def __init__(self: Self, begin: int, length: int, status: BlockStatus) -> None:
        self.begin = begin
        self.length = length
        self.status = status
        
        self.data: bytes = b""
    
    @property
    def is_available(self: Self) -> bool:
        return self.status is BlockStatus.AVAILABLE
    
    @property
    def is_missing(self: Self) -> bool:
        return self.status is BlockStatus.MISSING
    
    @property
    def is_requested(self: Self) -> bool:
        return self.status is BlockStatus.REQUESTED
    
    def set_status(self: Self, status: BlockStatus) -> None:
        self.status = status
    
    def set_status_as_missing(self: Self) -> None:
        self.set_status(BlockStatus.MISSING)
    
    def set_status_as_requested(self: Self) -> None:
        self.set_status(BlockStatus.REQUESTED)
    
    def set_status_as_available(self: Self) -> None:
        self.set_status(BlockStatus.AVAILABLE)
    
    def set_data(self: Self, data: bytes) -> None:
        self.data = data
    
    def clear_data(self: Self) -> None:
        self.data = b""
    
    def __repr__(self: Self) -> str:
        return f"Block(begin={self.begin}, length={self.length}, status={self.status})"