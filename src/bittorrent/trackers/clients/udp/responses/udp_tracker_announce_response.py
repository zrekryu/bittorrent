from dataclasses import dataclass


@dataclass
class UDPTrackerAnnounceResponse:
    interval: int
    leechers: int
    seeders: int
    peers: list[tuple[str, int]]
