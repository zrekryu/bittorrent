from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass


@dataclass(slots=True)
class TorrentAnnounceListTier:
    urls: list[str]

    def promote(self, url: str) -> None:
        try:
            self.urls.remove(url)
        except ValueError:
            raise ValueError(f"URL not found in this tier: {url}")

        self.urls.insert(0, url)

    def promote_index(self, index: int) -> None:
        try:
            url: str = self.urls.pop(index)
        except IndexError:
            raise IndexError("URL index out of range") from None

        self.urls.insert(0, url)

    @classmethod
    def from_list(cls, urls: Sequence[str]) -> TorrentAnnounceListTier:
        return cls(urls=list(urls))

    def __iter__(self) -> Iterator[str]:
        yield from self.urls

    def __getitem__(self, index: int | slice) -> str | list[str]:
        try:
            return self.urls[index]
        except IndexError:
            raise IndexError("URL index out of range") from None
