from enum import IntEnum, StrEnum


class HTTPTrackerEvent(StrEnum):
    STARTED = "started"
    STOPPED = "stopped"
    COMPLETED = "completed"


class UDPTrackerAction(IntEnum):
    CONNECT = 0
    ANNOUNCE = 1
    SCRAPE = 2
    ERROR = 3


class UDPTrackerEvent(IntEnum):
    COMPLETED = 1
    STOPPED = 2
    STARTED = 3
