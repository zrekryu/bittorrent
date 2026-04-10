from bencode import BencodeDataTypes
from bittorrent.exceptions import (
    TorrentMetadataInvalidTypeError,
    TorrentMetadataInvalidValueError,
    TorrentMetadataMissingKeyError,
)

from ..keys import SUPPORTED_INFO_KEYS
from ..models import (
    TorrentMetadataInfo,
    TorrentMetadataInfoFileEntry,
    TorrentMetadataInfoFileTree,
)
from .info_file_tree_parser import TorrentMetadataInfoFileTreeParser
from .info_files_parser import TorrentMetadataInfoFilesParser


class TorrentMetadataInfoParser:
    def __init__(self, info: dict[bytes, BencodeDataTypes]) -> None:
        if not isinstance(info, dict):
            raise TorrentMetadataInvalidTypeError(
                f"Info must be a dict, got {type(info).__name__} instead"
            )

        self.info = info

    def parse_name(self) -> str:
        key_utf8 = b"name.utf-8"
        key = key_utf8 if key_utf8 in self.info else b"name"
        name: BencodeDataTypes | None = self.info.get(key)

        if name is None:
            raise TorrentMetadataMissingKeyError(f"Missing info key: {key!r}")

        if not isinstance(name, bytes):
            raise TorrentMetadataInvalidTypeError(
                f"Info key {key!r} must be bytes, got {type(key).__name__} instead"
            )

        return name.decode("utf-8")

    def parse_piece_length(self) -> int:
        key = b"piece length"
        piece_length: BencodeDataTypes | None = self.info.get(key)

        if piece_length is None:
            raise TorrentMetadataMissingKeyError(f"Missing info key: {key!r}")

        if not isinstance(piece_length, int):
            raise TorrentMetadataInvalidTypeError(
                f"Info key {key!r} must be an int, got {type(piece_length).__name__} instead"
            )

        if piece_length < 0:
            raise TorrentMetadataInvalidValueError(
                f"Info key {key!r} must be a non-negative, got {piece_length} instead"
            )

        return piece_length

    def parse_pieces(self) -> bytes:
        key = b"pieces"
        pieces: BencodeDataTypes | None = self.info.get(key)

        if pieces is None:
            raise TorrentMetadataMissingKeyError(f"Missing info key: {key!r}")

        if not isinstance(pieces, bytes):
            raise TorrentMetadataInvalidTypeError(
                f"Info key {key!r} must be bytes, got {type(pieces).__name__} instead"
            )

        pieces_len_mod: int = len(pieces) % 20
        if pieces_len_mod != 0:
            raise TorrentMetadataInvalidValueError(
                f"Info key {key!r} must be a multiple of 20, got {pieces_len_mod} instead"
            )

        return pieces

    def parse_length(self) -> int:
        key = b"length"
        length: BencodeDataTypes | None = self.info.get(key)

        if length is None:
            raise TorrentMetadataMissingKeyError(f"Missing info key: {key!r}")

        if not isinstance(length, int):
            raise TorrentMetadataInvalidTypeError(
                f"Info key {key!r} must be an int, got {type(length).__name__} instead"
            )

        if length < 0:
            raise TorrentMetadataInvalidValueError(
                f"Info key {key!r} must be a non-negative integer, got {length} instead"
            )

        return length

    def parse_files(self) -> list[TorrentMetadataInfoFileEntry]:
        key = b"files"
        files: BencodeDataTypes | None = self.info.get(key)

        if files is None:
            raise TorrentMetadataMissingKeyError(f"Missing info key: {key!r}")

        files_parser = TorrentMetadataInfoFilesParser(files)
        return files_parser.parse_files()

    def parse_meta_version(self) -> int | None:
        key = b"meta version"
        meta_version: BencodeDataTypes | None = self.info.get(key)

        if meta_version is None:
            return None

        if not isinstance(meta_version, int):
            raise TorrentMetadataInvalidTypeError(
                f"Info key {key!r} must be an int, got {type(meta_version).__name__} instead"
            )

        if meta_version < 0:
            raise TorrentMetadataInvalidValueError(
                f"Info key {key!r} must be non-negative, got {meta_version} instead"
            )

        return meta_version

    def parse_file_tree(self) -> TorrentMetadataInfoFileTree:
        key = b"file tree"
        file_tree: BencodeDataTypes | None = self.info.get(key)

        if file_tree is None:
            raise TorrentMetadataMissingKeyError(f"Missing info key: {key!r}")

        file_tree_parser = TorrentMetadataInfoFileTreeParser(file_tree)
        return file_tree_parser.parse_file_tree()

    def parse_private(self) -> int | None:
        key = b"private"
        private: BencodeDataTypes | None = self.info.get(key)

        if private is None:
            return None

        if not isinstance(private, int):
            raise TorrentMetadataInvalidTypeError(
                f"Info key {key!r} must be an int, got {type(private).__name__} instead"
            )

        if private not in (0, 1):
            raise TorrentMetadataInvalidValueError(
                f"Info key {key!r} must be either 0 or 1, not {private}"
            )

        return private

    def extract_extra_keys(self) -> dict[bytes, BencodeDataTypes]:
        return {
            key: value
            for key, value in self.info.items()
            if key not in SUPPORTED_INFO_KEYS
        }

    def parse(self, extract_extra_keys: bool = True) -> TorrentMetadataInfo:
        pieces: bytes | None = None
        length: int | None = None
        files: list[TorrentMetadataInfoFileEntry] | None = None

        file_tree: TorrentMetadataInfoFileTree | None = None

        if b"pieces" in self.info:
            pieces = self.parse_pieces()

            if b"length" in self.info:
                length = self.parse_length()
            elif b"files" in self.info:
                files = self.parse_files()
            else:
                raise TorrentMetadataMissingKeyError(
                    "Missing info key: either 'length' or 'files' must be present"
                )

        if b"file tree" in self.info:
            file_tree = self.parse_file_tree()

        if pieces is None and file_tree is None:
            raise TorrentMetadataMissingKeyError(
                "Missing info key: either 'pieces' or 'file tree' must be present"
            )

        return TorrentMetadataInfo(
            name=self.parse_name(),
            piece_length=self.parse_piece_length(),
            pieces=pieces,
            length=length,
            files=files,
            **({"meta_version": meta_version} if (meta_version := self.parse_meta_version()) else {}),  # type: ignore[arg-type]
            file_tree=file_tree,
            private=bool(self.parse_private()),
            **({"extra_keys": self.extract_extra_keys()} if extract_extra_keys else {}),  # type: ignore[arg-type]
        )
