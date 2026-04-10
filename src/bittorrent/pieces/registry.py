import math
from collections.abc import Buffer, Iterator
from typing import ClassVar, Final

from .block import Block
from .piece import Piece


class PieceRegistry:
    BLOCK_SIZE: ClassVar[Final[int]] = 2**14

    def __init__(
        self,
        piece_length: int,
        pieces_hash: Buffer,
        total_length: int,
        block_size: int | None = None
    ) -> None:
        self.piece_length = piece_length
        self.pieces_hash = memoryview(pieces_hash)
        self.total_length = total_length
        self.block_size = block_size or self.BLOCK_SIZE

        self.last_piece_length = self.total_length % self.piece_length or self.piece_length
        self.last_piece_uneven: bool = self.last_piece_length != self.piece_length

        self.num_pieces = math.ceil(self.total_length / self.piece_length)
        self.blocks_per_piece = self.piece_length // self.block_size

        self.blocks_in_last_piece = math.ceil(self.last_piece_length / self.block_size)
        self.last_block_size = self.last_piece_length % self.block_size or self.block_size

        self.pieces: list[Piece] = self._create_pieces()

    def get_piece(self, index: int) -> Piece:
        try:
            return self.pieces[index]
        except IndexError:
            raise IndexError(
                f"Piece index {index} out of range (0 to {self.num_pieces - 1})"
            ) from None

    def get_incomplete_pieces(self) -> Iterator[Piece]:
        return (piece for piece in self.pieces if not piece.is_complete)

    def get_complete_pieces(self) -> Iterator[Piece]:
        return (piece for piece in self.pieces if piece.is_complete)

    @property
    def all_pieces_complete(self) -> bool:
        return all(piece.is_complete for piece in self.pieces)

    def get_block(self, index: int, offset: int) -> Block:
        piece = self.get_piece(index)
        return piece.get_block(offset)

    def mark_block_missing(self, index: int, offset: int) -> None:
        block = self.get_block(index, offset)
        block.mark_missing()

    def mark_block_requested(self, index: int, offset: int) -> None:
        block = self.get_block(index, offset)
        block.mark_requested()

    def mark_block_available(self, index: int, offset: int) -> None:
        block = self.get_block(index, offset)
        block.mark_available()

    def _generate_blocks_per_piece(self) -> dict[int, Block]:
        blocks: dict[int, Block] = {}
        for index in range(self.blocks_per_piece):
            offset = index * self.block_size

            blocks[offset] = Block(
                offset=offset,
                size=self.block_size,
                is_last=(index == (self.blocks_per_piece - 1))
            )

        return blocks

    def _generate_blocks_in_last_piece(self) -> dict[int, Block]:
        blocks: dict[int, Block] = {}
        for index in range(self.blocks_in_last_piece):
            offset = index * self.block_size
            is_last: bool = (index == (self.blocks_in_last_piece - 1))

            blocks[offset] = Block(
                offset=offset,
                size=self.last_block_size if is_last else self.block_size,
                is_last=is_last
            )

        return blocks

    def _create_pieces(self) -> list[Piece]:
        pieces: list[Piece] = []
        for index in range(self.num_pieces):
            is_last: bool = (index == (self.num_pieces - 1))

            if is_last and self.last_piece_uneven:
                blocks = self._generate_blocks_in_last_piece()
            else:
                blocks = self._generate_blocks_per_piece()

            hash_start = index * 20
            hash_end = hash_start + 20

            piece = Piece(
                index=index,
                length=self.last_piece_length if is_last else self.piece_length,
                piece_hash=self.pieces_hash[hash_start:hash_end],
                blocks=blocks,
                is_last=is_last
            )
            pieces.append(piece)

        return pieces
