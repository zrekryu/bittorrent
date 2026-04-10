from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TorrentMetadataDHTNode:
    hostname: str
    port: int

    def to_list(self) -> list[str | int]:
        return [self.hostname, self.port]

    def to_tuple(self) -> tuple[str, int]:
        return (self.hostname, self.port)
