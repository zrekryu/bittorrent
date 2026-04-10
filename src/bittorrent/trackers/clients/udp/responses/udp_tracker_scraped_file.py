class UDPTrackerScrapedFile:
    def __init__(self, seeders: int, completed: int, leechers: int) -> None:
        self.seeders = seeders
        self.completed = completed
        self.leechers = leechers

    def __repr__(self) -> str:
        return (
            "UDPTrackerScrapedFile("
            f"seeders={self.seeders}, "
            f"completed={self.completed}, "
            f"leechers={self.leechers}"
            ")"
        )
