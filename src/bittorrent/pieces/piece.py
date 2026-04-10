from collections.abc import Buffer, Iterator, Mapping

from .block import Block


class Piece:
    __slots__ = ("index", "length", "piece_hash", "blocks", "is_last")

    def __init__(
        self,
        index: int,
        length: int,
        piece_hash: Buffer,
        blocks: Mapping[int, Block],
        is_last: bool = False
    ) -> None:
        self.index = index
        self.length = length
        self.piece_hash = memoryview(piece_hash)
        self.blocks: dict[int, Block] = dict(blocks) if not isinstance(blocks, dict) else blocks
        self.is_last = is_last

    def verify_hash(self, piece_hash: Buffer) -> bool:
        return self.piece_hash == memoryview(piece_hash)

    @property
    def is_missing(self) -> bool:
        return any(block.is_missing for block in self.blocks.values())

    @property
    def is_partial(self) -> bool:
        return (
            any(block.is_available for block in self.blocks.values())
            and not self.is_complete
        )

    @property
    def is_complete(self) -> bool:
        return all(block.is_available for block in self.blocks.values())

    def get_block(self, offset: int) -> Block:
        try:
            return self.blocks[offset]
        except IndexError:
            raise IndexError(f"Block offset {offset} not found") from None

    def get_missing_blocks(self) -> Iterator[Block]:
        return (block for block in self.blocks.values() if block.is_missing)

    def get_requested_blocks(self) -> Iterator[Block]:
        return (block for block in self.blocks.values() if block.is_requested)

    def get_available_blocks(self) -> Iterator[Block]:
        return (block for block in self.blocks.values() if block.is_available)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Piece):
            return NotImplemented

        return self.index == other.index

    def __hash__(self) -> int:
        return hash(self.index)

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}("
            f"index={self.index}, "
            f"length={self.length}, "
            f"piece_hash={self.piece_hash!r}, "
            f"blocks={self.blocks}, "
            f"is_last={self.is_last}"
            ")"
        )