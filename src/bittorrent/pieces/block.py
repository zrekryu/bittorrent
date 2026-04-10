from bittorrent.enums import BlockState


class Block:
    __slots__ = ("offset", "size", "state", "is_last")

    def __init__(
        self,
        offset: int,
        size: int,
        state: BlockState = BlockState.MISSING,
        is_last: bool = False
    ) -> None:
        self.offset = offset
        self.size = size
        self.state = state
        self.is_last = is_last

    def mark_missing(self) -> None:
        self.state = BlockState.MISSING

    def mark_requested(self) -> None:
        self.state = BlockState.REQUESTED

    def mark_available(self) -> None:
        self.state = BlockState.AVAILABLE

    @property
    def is_missing(self) -> bool:
        return self.state == BlockState.MISSING

    @property
    def is_requested(self) -> bool:
        return self.state == BlockState.REQUESTED

    @property
    def is_available(self) -> bool:
        return self.state == BlockState.AVAILABLE

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}("
            f"offset={self.offset}, "
            f"size={self.size}, "
            f"state={self.state}, "
            f"is_last={self.is_last}"
            ")"
        )