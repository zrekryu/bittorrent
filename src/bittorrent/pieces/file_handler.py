from hashlib import md5
from pathlib import Path
from typing import Self, TypedDict

class FileEntry(TypedDict):
    length: int
    path: list[bytes]
    md5sum: bytes | None

class FileHandler:
    def __init__(self: Self, name: str, piece_length: int, path: str, files: list[FileEntry] | None = None) -> None:
        self.name = name
        self.piece_length = piece_length
        self.path: str = path
        self.files = files
        
        self.file_offsets: list[tuple[int, int, int]] | None = self.calc_file_offsets() if files else None
    
    def calc_file_offsets(self: Self) -> list[tuple[int, int, int]]:
        return [
            (index, current_offset, current_offset + file[b"length"] - 1)
            for file in files
            ]
    
    def get_files_by_offset(self: Self, offset: int) -> list[FileEntry]:
        files: list[FileEntry] = []
        remaining_length: int = self.piece_length
        while remaining_length:
            for file_index, start_offset, end_offset in self.file_offsets:
                if start_offset <= offset <= end_offset:
                    files.append(self.files[file_index])
                    
                    bytes_in_file: int = end_offset - offset + 1
                    remaining_length -= bytes_in_file
                    
                    if remaining_length <= 0:
                        break
                    
                    offset = end_offset + 1
    
    async def write_data(self: Self, path: str, offset: int, data: bytes) -> None:
        async with aiofiles.open(path=path, mode="r+b") as fobj:
            await fobj.seek(offset)
            await fobj.write(data)
    
    async def write_piece(self: Self, index: int, begin: int, data: bytes) -> None:
        if self.files:
            await self.write_piece_multiple_files(index, begin, data)
        else:
            await self.write_piece_single_file(index, begin, data)
    
    async def write_piece_single_file(self: Self, index: int, begin: int, data: bytes) -> None:
        path_obj: Path = Path(self.path, self.name)
        path_obj.touch()
        
        offset: int = self.piece_length * index
        await self.write_data(str(path_obj), offset, data)
    
    async def write_piece_multiple_files(self: Self, index: int, begin: int, data: bytes) -> None:
        offset: int = self.piece_length * index
        for file in self.get_files_by_offset(offset):
            if "md5" in file:
                md5_checksum: str = file[b"md5"].decode("utf-8")
                if not self.verify_md5checksum(md5_checksum, data):
                    raise IOError("MD5 checksum does not match")
            
            path_obj: Path = Path(self.path, self.name, *(p.decode("utf-8") for p in file[b"path"]))
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.touch(exist_ok=True)
            
            await self.write_data(str(path_obj), file_offset, data)
    
    @staticmethod
    def verify_md5checksum(md5_checksum: str, data: bytes) -> bool:
        calculated_md5: str = md5(data).digest()
        return calculated_md5 == md5_checksum