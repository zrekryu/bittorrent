from dataclasses import dataclass


@dataclass
class HTTPTrackerAnnounceResponse:
    interval: int
    complete: int | None = None
    incomplete: int | None = None

    peers: list[tuple[str, int]] | None = None
    peers6: list[tuple[str, int]] | None = None

    min_interval: int | None = None
    tracker_id: str | None = None

    warning_message: str | None = None
