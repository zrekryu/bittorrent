from pathlib import Path
from typing import Any, cast

from bencode import BencodeDataTypes
from bittorrent.exceptions import (
    TorrentMetadataInvalidTypeError,
    TorrentMetadataInvalidValueError,
    TorrentMetadataMissingKeyError,
)

from ..keys import SUPPORTED_V1_INFO_FILE_KEYS
from ..models import TorrentMetadataInfoFileEntry


class TorrentMetadataInfoFilesParser:
    def __init__(self, files: BencodeDataTypes) -> None:
        if not isinstance(files, list):
            raise TorrentMetadataInvalidTypeError(
                f"Files must be a list, got {type(files).__name__} instead"
            )

        for file_index, file in enumerate(files):
            if not isinstance(file, dict):
                raise TorrentMetadataInvalidTypeError(
                    f"File must be a dict, got {type(file).__name__} instead (file index: {file_index})"
                )

        self.files: list[dict[bytes, BencodeDataTypes]] = cast(
            list[dict[bytes, BencodeDataTypes]], files
        )

    def parse_length(self, file: dict[bytes, BencodeDataTypes], file_index: int) -> int:
        key = b"length"
        length: BencodeDataTypes | None = file.get(key)

        if length is None:
            raise TorrentMetadataMissingKeyError(
                f"Missing info file key: {key!r} (file index: {file_index})"
            )

        if not isinstance(length, int):
            raise TorrentMetadataInvalidTypeError(
                f"Info file key {key!r} must be an int, got {type(length).__name__} instead (file index: {file_index})"
            )

        if length < 0:
            raise TorrentMetadataInvalidValueError(
                f"Info file key {key!r} must be a non-negative integer, got {length} instead (file index: {file_index})"
            )

        return length

    def parse_path(self, file: dict[bytes, BencodeDataTypes], file_index: int) -> Path:
        key = b"path.utf-8" if b"path.utf-8" in file else b"path"

        raw_path: BencodeDataTypes | None = file.get(key)
        if raw_path is None:
            raise TorrentMetadataMissingKeyError(
                f"Missing info file key: {key!r} (file index: {file_index})"
            )

        if not isinstance(raw_path, list):
            raise TorrentMetadataInvalidTypeError(
                f"Info file key {key!r} must be a list, got {type(raw_path).__name__} instead (file index: {file_index})"
            )

        path_parts: list[str] = []
        for i, p in enumerate(raw_path):
            if not isinstance(p, bytes):
                raise TorrentMetadataInvalidTypeError(
                    f"Info file key {key!r} must be bytes, got {type(p).__name__} instead (file index: {file_index})"
                )

            path_parts.append(p.decode("utf-8"))

        return Path(*path_parts)

    def extract_extra_keys(self, file: dict[bytes, Any]) -> dict[bytes, Any]:
        return {
            key: value
            for key, value in file.items()
            if key not in SUPPORTED_V1_INFO_FILE_KEYS
        }

    def parse_files(
        self, extract_extra_keys: bool = True
    ) -> list[TorrentMetadataInfoFileEntry]:
        return [
            TorrentMetadataInfoFileEntry(
                length=self.parse_length(file, file_index),
                path=self.parse_path(file, file_index),
                **(
                    {"extra_keys": self.extract_extra_keys(file)}
                    if extract_extra_keys
                    else {}
                ),
            )
            for file_index, file in enumerate(self.files)
        ]
