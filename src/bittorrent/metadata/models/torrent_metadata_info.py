from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from bencode import BencodeDataTypes, BencodeSerializableTypes

from .torrent_metadata_info_file_entry import TorrentMetadataInfoFileEntry
from .torrent_metadata_info_file_tree import TorrentMetadataInfoFileTree


@dataclass(frozen=True, slots=True)
class TorrentMetadataInfo:
    name: str
    piece_length: int
    pieces: bytes | None
    length: int | None
    files: tuple[TorrentMetadataInfoFileEntry, ...] | None
    meta_version: int
    file_tree: TorrentMetadataInfoFileTree | None
    private: bool
    extra_keys: MappingProxyType[bytes, BencodeDataTypes]

    def __init__(
        self,
        name: str,
        piece_length: int,
        pieces: bytes | None = None,
        length: int | None = None,
        files: Sequence[TorrentMetadataInfoFileEntry] | None = None,
        meta_version: int = 1,
        file_tree: TorrentMetadataInfoFileTree | None = None,
        private: bool = False,
        extra_keys: Mapping[bytes, BencodeDataTypes] | None = None,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "piece_length", piece_length)
        object.__setattr__(self, "pieces", pieces)
        object.__setattr__(self, "length", length)
        object.__setattr__(self, "files", tuple(files) if files is not None else None)
        object.__setattr__(self, "meta_version", meta_version)
        object.__setattr__(self, "file_tree", file_tree)
        object.__setattr__(self, "private", private)
        object.__setattr__(self, "extra_keys", MappingProxyType(extra_keys or {}))

    def to_dict(
        self,
        v1: bool = True,
        v2: bool = True,
        merge_extra_keys: bool = True,
    ) -> dict[str | bytes, BencodeSerializableTypes]:
        info: dict[str | bytes, BencodeSerializableTypes] = {
            "name": self.name,
            "piece length": self.piece_length,
        }

        if v1 and self.pieces is not None:
            info["pieces"] = self.pieces

            if self.length is not None:
                info["length"] = self.length
            if self.files is not None:
                info["files"] = [file.to_dict(merge_extra_keys) for file in self.files]

        if v2 and self.file_tree is not None:
            info["meta version"] = self.meta_version
            info["file tree"] = cast(
                dict[str | bytes, BencodeSerializableTypes], self.file_tree.to_dict()
            )

        if self.private:
            info["private"] = self.private

        if merge_extra_keys:
            info.update(
                cast(dict[str | bytes, BencodeSerializableTypes], self.extra_keys)
            )
        else:
            info["extra_keys"] = cast(
                dict[str | bytes, BencodeSerializableTypes], self.extra_keys
            )

        return info

    def to_v1_dict(
        self, merge_extra_keys: bool = True
    ) -> dict[str | bytes, BencodeSerializableTypes]:
        return self.to_dict(v2=False, merge_extra_keys=merge_extra_keys)

    def to_v2_dict(
        self, merge_extra_keys: bool = True
    ) -> dict[str | bytes, BencodeSerializableTypes]:
        return self.to_dict(v1=False, merge_extra_keys=merge_extra_keys)
