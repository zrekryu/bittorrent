from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import cast

from bencode import BencodeDataTypes, BencodeSerializableTypes


@dataclass(frozen=True, slots=True)
class TorrentMetadataInfoFileEntry:
    length: int
    path: Path
    extra_keys: Mapping[bytes, BencodeDataTypes] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if self.extra_keys is not None:
            object.__setattr__(self, "extra_keys", MappingProxyType(self.extra_keys))

    def to_dict(
        self, merge_extra_keys: bool = True
    ) -> dict[str | bytes, BencodeSerializableTypes]:
        file: dict[str | bytes, BencodeSerializableTypes] = {
            "length": self.length,
            "path": list(self.path.parts),
        }

        if merge_extra_keys:
            file.update(
                cast(dict[str | bytes, BencodeSerializableTypes], self.extra_keys)
            )

        return file
