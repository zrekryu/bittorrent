from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from .torrent_announce_list_tier import TorrentAnnounceListTier


@dataclass(slots=True)
class TorrentAnnounceList:
    tiers: list[TorrentAnnounceListTier]

    def to_list(self) -> list[list[str]]:
        return [tier.urls for tier in self.tiers]

    @classmethod
    def from_list(cls, announce_list: Sequence[Sequence[str]]) -> TorrentAnnounceList:
        return cls(
            tiers=[TorrentAnnounceListTier.from_list(tier) for tier in announce_list]
        )

    def __iter__(self) -> Iterator[tuple[TorrentAnnounceListTier, str]]:
        for tier in self.tiers:
            for url in tier:
                yield tier, url
