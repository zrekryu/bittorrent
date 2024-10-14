from hashlib import md5
from pathlib import Path
from typing import Self, TypedDict

class FileEntry(TypedDict):
    length: int
    path: list[bytes]
    md5sum: bytes | None
    
    offset: int | None = None  # Created by FileHandler.get_files_by_piece_index().

class FileHandler:
    def __init__(
        self: Self,
        name: str,
        piece_length: int,
        last_piece_length: int,
        last_piece_index: int,
        path: str,
        files: list[FileEntry] | None = None
        ) -> None:
        self.name = name
        self.piece_length = piece_length
        self.last_piece_length = last_piece_length
        self.last_piece_index = last_piece_index
        self.path = path
        self.files = files
        
        self.file_offsets: list[tuple[int, int, int]] | None = self.calc_file_offsets() if self.files else None
    
    def calc_file_offsets(self: Self) -> list[tuple[int, int, int]]:
        current_offset: int = 0
        file_offsets: list[tuple[int, int, int]] = []
        for index, file in enumerate(self.files):
            end_offset: int = current_offset + file[b"length"] - 1
            file_offsets.append(
                (index, current_offset, end_offset)
                )
            current_offset += file[b"length"]
        
        return file_offsets
    
    def get_files_by_piece_index(self: Self, piece_index: int) -> list[tuple[FileEntry, int]]:
        files: list[FileEntry] = []
        offset: int = piece_index * self.piece_length
        remaining_length: int = self.last_piece_length if piece_index == self.last_piece_index else self.piece_length
        while remaining_length:
            for file_index, start_offset, end_offset in self.file_offsets:
                if start_offset <= offset <= end_offset:
                    self.files[file_index]["offset"] = offset - start_offset
                    files.append(self.files[file_index])
                    
                    remaining_length -= end_offset - offset + 1
                    
                    if remaining_length <= 0:
                        break
                    
                    offset = end_offset + 1
        return files
    
    async def write_data(self: Self, path: str, offset: int, data: bytes) -> None:
        async with aiofiles.open(path=path, mode="r+b") as file:
            await file.seek(offset)
            await file.write(data)
    
    async def write_piece(self: Self, index: int, piece: bytes) -> None:
        if self.files:
            await self.write_piece_on_multiple_files(index, piece)
        else:
            await self.write_piece_on_single_file(index, piece)
    
    async def write_piece_on_single_file(self: Self, index: int, piece: bytes) -> None:
        path_obj: Path = Path(self.path, self.name)
        path_obj.touch()
        
        offset: int = self.piece_length * index
        await self.write_data(str(path_obj), offset, piece)
    
    async def write_piece_on_multiple_files(self: Self, index: int, piece: bytes) -> None:
        for file in self.get_files_by_piece_index(index):
            path_obj: Path = Path(self.path, self.name, *(p.decode("utf-8") for p in file[b"path"]))
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.touch(exist_ok=True)
            
            await self.write_data(str(path_obj), file["offset"], piece)