from dataclasses import dataclass


@dataclass
class HTTPTrackerScrapedFile:
    complete: int
    downloaded: int
    incomplete: int
    name: str | None = None
