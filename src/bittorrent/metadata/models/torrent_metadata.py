from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import cast

from bencode import BencodeDataTypes, BencodeSerializableTypes

from .torrent_metadata_dht_node import TorrentMetadataDHTNode
from .torrent_metadata_info import TorrentMetadataInfo


@dataclass(frozen=True, slots=True)
class TorrentMetadata:
    info: TorrentMetadataInfo
    announce: str | None
    announce_list: tuple[tuple[str, ...], ...] | None
    url_list: tuple[str, ...] | None
    nodes: tuple[TorrentMetadataDHTNode, ...] | None
    creation_date: datetime | None
    created_by: str | None
    comment: str | None
    piece_layers: MappingProxyType[bytes, bytes]
    extra_keys: MappingProxyType[bytes, BencodeDataTypes]

    def __init__(
        self,
        info: TorrentMetadataInfo,
        announce: str | None = None,
        announce_list: Sequence[Sequence[str]] | None = None,
        url_list: Sequence[str] | None = None,
        nodes: Sequence[TorrentMetadataDHTNode] | None = None,
        creation_date: datetime | None = None,
        created_by: str | None = None,
        comment: str | None = None,
        piece_layers: Mapping[bytes, bytes] | None = None,
        extra_keys: Mapping[bytes, BencodeDataTypes] | None = None,
    ) -> None:
        object.__setattr__(self, "info", info)
        object.__setattr__(self, "announce", announce)

        if announce_list is not None:
            object.__setattr__(
                self,
                "announce_list",
                tuple(tuple(tier) for tier in announce_list)
                if announce_list is not None
                else None,
            )

        object.__setattr__(
            self, "url_list", tuple(url_list) if url_list is not None else None
        )
        object.__setattr__(self, "nodes", tuple(nodes) if nodes is not None else None)
        object.__setattr__(self, "creation_date", creation_date)
        object.__setattr__(self, "created_by", created_by)
        object.__setattr__(self, "comment", comment)
        object.__setattr__(self, "piece_layers", MappingProxyType(piece_layers or {}))
        object.__setattr__(self, "extra_keys", MappingProxyType(extra_keys or {}))

    def to_dict(
        self, merge_extra_keys: bool = True
    ) -> dict[bytes | str, BencodeSerializableTypes]:
        metadata: dict[str | bytes, BencodeSerializableTypes] = {
            "info": self.info.to_dict(merge_extra_keys)
        }
        if self.announce is not None:
            metadata["announce"] = self.announce
        if self.announce_list is not None:
            metadata["announce-list"] = self.announce_list
        if self.url_list is not None:
            metadata["url-list"] = self.url_list
        if self.nodes is not None:
            metadata["nodes"] = [node.to_list() for node in self.nodes]
        if self.creation_date is not None:
            metadata["creation date"] = int(self.creation_date.timestamp())
        if self.created_by is not None:
            metadata["created by"] = self.created_by
        if self.comment is not None:
            metadata["comment"] = self.comment
        if self.piece_layers is not None:
            metadata["piece layers"] = cast(
                dict[str | bytes, BencodeSerializableTypes], self.piece_layers
            )

        if merge_extra_keys:
            metadata.update(
                cast(dict[str | bytes, BencodeSerializableTypes], self.extra_keys)
            )
        else:
            metadata["extra_keys"] = cast(
                dict[str | bytes, BencodeSerializableTypes], self.extra_keys
            )

        return metadata
