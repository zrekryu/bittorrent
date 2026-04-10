from enum import StrEnum


class BlockState(StrEnum):
    MISSING = "missing"
    REQUESTED = "requested"
    AVAILABLE = "available"
