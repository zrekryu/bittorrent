from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final

from bittorrent.enums import PeerSourceKind


class PeerSource(ABC):
    @property
    @abstractmethod
    def kind(self) -> str: ...


@dataclass(frozen=True, slots=True)
class TrackerPeerSource(PeerSource):
    announce_url: str

    @property
    def kind(self) -> str:
        return PeerSourceKind.TRACKER


@dataclass(frozen=True, slots=True)
class UnknownPeerSource(PeerSource):
    @property
    def kind(self) -> str:
        return PeerSourceKind.UNKNOWN


UNKNOWN_PEER_SOURCE: Final[UnknownPeerSource] = UnknownPeerSource()