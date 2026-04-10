from typing import Final

from bencode import BencodeDataTypes
from bittorrent.exceptions import (
    TorrentMetadataInvalidTypeError,
)

from ..models import TorrentMetadataInfoFileTree

FILE_NODE_INDICATOR: Final[bytes] = b""


class TorrentMetadataInfoFileTreeParser:
    def __init__(self, file_tree: BencodeDataTypes) -> None:
        if not isinstance(file_tree, dict):
            raise TorrentMetadataInvalidTypeError(
                f"file_tree must be a dict, got {type(file_tree).__name__} instead"
            )

        self.file_tree: dict[bytes, BencodeDataTypes] = file_tree

    def parse_file_tree(self) -> TorrentMetadataInfoFileTree:
        return TorrentMetadataInfoFileTree()
