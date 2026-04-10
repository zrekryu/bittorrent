from __future__ import annotations

from datetime import datetime
from functools import cached_property
from types import MappingProxyType

import aiofiles
import bencode
from bittorrent.exceptions import TorrentMetadataInvalidTypeError
from bittorrent.utils import (
    calculate_torrent_total_length,
    generate_info_hash_sha1,
    generate_info_hash_sha256,
)

from .models import TorrentMetadata, TorrentMetadataDHTNode, TorrentMetadataInfo
from .parsers import TorrentMetadataParser


class Torrent:
    def __init__(self, metadata: TorrentMetadata) -> None:
        self.metadata = metadata

    @property
    def info(self) -> TorrentMetadataInfo:
        return self.metadata.info

    @property
    def announce(self) -> str | None:
        return self.metadata.announce

    @property
    def announce_list(self) -> tuple[tuple[str, ...], ...] | None:
        return self.metadata.announce_list

    @property
    def url_list(self) -> tuple[str, ...] | None:
        return self.metadata.url_list

    @property
    def nodes(self) -> tuple[TorrentMetadataDHTNode, ...] | None:
        return self.metadata.nodes

    @property
    def creation_date(self) -> datetime | None:
        return self.metadata.creation_date

    @property
    def created_by(self) -> str | None:
        return self.metadata.created_by

    @property
    def comment(self) -> str | None:
        return self.metadata.comment

    @property
    def piece_layers(self) -> MappingProxyType[bytes, bytes] | None:
        return self.metadata.piece_layers

    @property
    def extra_keys(self) -> MappingProxyType[bytes, bencode.BencodeDataTypes]:
        return self.metadata.extra_keys

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def version(self) -> int:
        return self.info.meta_version

    @property
    def is_v1(self) -> bool:
        return self.info.pieces is not None

    @property
    def is_v2(self) -> bool:
        return self.info.file_tree is not None

    @property
    def is_hybrid(self) -> bool:
        return self.is_v1 and self.is_v2

    @property
    def is_multifile(self) -> bool:
        return self.info.files is not None

    @cached_property
    def total_length(self) -> int:
        return calculate_torrent_total_length(self.info)

    @cached_property
    def info_hash_sha1(self) -> bytes:
        return generate_info_hash_sha1(self.info.to_v1_dict())

    @cached_property
    def info_hash_sha256(self) -> bytes:
        return generate_info_hash_sha256(self.info.to_v2_dict())

    @property
    def info_hash(self) -> bytes:
        if self.is_v2:
            return self.info_hash_sha256
        else:
            return self.info_hash_sha1

    @classmethod
    async def from_path(cls, path: str) -> Torrent:
        async with aiofiles.open(path, mode="rb") as file:
            content = await file.read()

        decoded_metadata: bencode.BencodeDataTypes = bencode.decode(content)
        if not isinstance(decoded_metadata, dict):
            raise TorrentMetadataInvalidTypeError(
                f"Torrent metadata must be a dict, got {type(decoded_metadata).__name__} instead"
            )

        parser = TorrentMetadataParser(metadata=decoded_metadata)

        return cls(metadata=parser.parse())

    def to_dict(
        self, merge_extra_keys: bool = True
    ) -> dict[str | bytes, bencode.BencodeSerializableTypes]:
        return self.metadata.to_dict(merge_extra_keys)

    def to_bencode(self, merge_extra_keys: bool = True) -> bytes:
        return bencode.encode(self.to_dict(merge_extra_keys))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Torrent):
            return NotImplemented

        if self.is_v2 and other.is_v2:
            return self.info_hash_sha256 == other.info_hash_sha256
        else:
            return self.info_hash_sha1 == other.info_hash_sha1

    def __hash__(self) -> int:
        return hash(self.info_hash)

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}("
            f"name={self.name}, "
            f"total_length={self.total_length}, "
            f"is_multifile={self.is_multifile}, "
            f"version={self.version}, "
            f"is_hybrid={self.is_hybrid}"
            ")"
        )