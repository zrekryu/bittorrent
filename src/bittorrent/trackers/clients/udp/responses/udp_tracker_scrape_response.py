from dataclasses import dataclass

from .udp_tracker_scraped_file import UDPTrackerScrapedFile


@dataclass
class UDPTrackerScrapeResponse:
    files: list[UDPTrackerScrapedFile]
