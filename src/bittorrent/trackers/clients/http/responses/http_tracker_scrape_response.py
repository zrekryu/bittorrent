from dataclasses import dataclass

from .http_tracker_scraped_file import HTTPTrackerScrapedFile


@dataclass
class HTTPTrackerScrapeResponse:
    files: dict[bytes, HTTPTrackerScrapedFile]
