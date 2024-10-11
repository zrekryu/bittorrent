from enum import Enum, IntEnum, StrEnum

class TrackerHTTPEvent(StrEnum):
    STARTED: str = "started"
    STOPPED: str = "stopped"
    COMPLETED: str = "completed"

class TrackerUDPEvent(IntEnum):
    COMPLETED: int = 1
    STARTED: int = 2
    STOPPED: int = 3

class TrackerUDPAction(IntEnum):
    CONNECT: int = 0
    ANNOUNCE: int = 1

class ProtocolString(Enum):
    BITTORRENT_PROTOCOL_V1: bytes = b"BitTorrent protocol"

class PeerStatus(StrEnum):
    CHOKING: str = "choking"
    INTERESTED: str = "interested"
    
    AM_CHOKING: str = "choking"
    AM_INTERESTED: str = "interested"

class BlockStatus(StrEnum):
    MISSING: str = "missing"
    REQUESTED: str = "requested"
    AVAILABLE: str = "available"