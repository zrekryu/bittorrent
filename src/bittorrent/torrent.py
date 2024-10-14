from datetime import datetime
import math
from typing import Any, Self

import aiofiles
import libbencode

class Torrent:
    def __init__(self: Self, data: bytes) -> None:
        self.metadata: dict[bytes, Any] = libbencode.decode(data)
        
        self.announce: bytes = self.metadata[b"announce"]
        self.announce_list: list[list[bytes]] = self.metadata[b"announce-list"]
        
        self.info: dict[bytes, Any] = self.metadata[b"info"]
        
        self.url_list: list[bytes] | None = self.metadata.get(b"url-list")
        
        self.created_by: str | None = self.metadata.get(b"created by")
        self.creation_date: datetime | None = datetime.utcfromtimestamp(creation_date) if (creation_date := self.metadata.get(b"creation date")) else None
        
        self.comment: bytes | None = self.metadata.get(b"comment")
        
        self.name: str = self.info[b"name"].decode("utf-8")
        
        self.piece_length: int = self.info[b"piece length"]
        self.total_length: int = sum((file[b"length"] for file in self.info[b"files"])) if b"files" in self.info else self.info[b"length"]
        self.last_piece_length: int = self.total_length % self.piece_length
        self.total_pieces: int = math.ceil(self.total_length / self.piece_length)
        self.last_piece_index: int = self.total_pieces - 1
        
        self.is_private: bool = bool(self.info.get(b"private"))
        
        self.has_multiple_files: bool = b"files" in self.info
    
    @classmethod
    async def from_file(cls: type[Self], path: str) -> None:
        async with aiofiles.open(path, mode="rb") as file:
            return cls(await file.read())
    
    def __repr__(self: Self) -> str:
        return f"Torrent(name={self.name})"