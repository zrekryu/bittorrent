from __future__ import annotations

from collections.abc import Buffer, Iterator


class PeerBitfield:
    __slots__ = ("data", "num_pieces", "num_bytes")


    def __init__(self, data: Buffer, num_pieces: int, num_bytes: int) -> None:
        self.data = bytearray(data)
        self.num_pieces = num_pieces
        self.num_bytes = num_bytes

    @classmethod
    def create(cls, num_pieces: int, *, all_pieces_set: bool = False) -> PeerBitfield:
        num_bytes = (num_pieces + 7) // 8

        if all_pieces_set:
            data = bytearray(b"\xFF" * num_bytes)

            if used_bits := num_pieces % 8:
                spare_bits = 8 - used_bits
                mask = (0xFF << spare_bits) & 0xFF
                data[-1] &= mask

            return cls(data, num_pieces, num_bytes)

        return cls(bytearray(num_bytes), num_pieces, num_bytes)

    @classmethod
    def empty(cls, num_pieces: int) -> PeerBitfield:
        return cls.create(num_pieces)

    @classmethod
    def full(cls, num_pieces: int) -> PeerBitfield:
        return cls.create(num_pieces, all_pieces_set=True)

    def set_data(self, data: Buffer) -> None:
        view = memoryview(data)
        length = len(view)
        if length != self.num_bytes:
            raise ValueError(
                f"data must be exactly {self.num_bytes} bytes (got {length})"
            )

        self.data[:] = view

    def has_piece(self, index: int) -> bool:
        self._check_range(index)

        byte_index = index // 8
        bit_index = 7 - (index % 8)

        mask = 1 << bit_index
        result = self.data[byte_index] & mask

        return bool(result)

    def set_piece(self, index: int) -> None:
        self._check_range(index)

        byte_index = index // 8
        bit_index = 7 - (index % 8)

        mask = 1 << bit_index
        self.data[byte_index] |= mask

    def clear_piece(self, index: int) -> None:
        self._check_range(index)

        byte_index = index // 8
        bit_index = 7 - (index % 8)

        mask = 1 << bit_index
        self.data[byte_index] &= ~mask

    def clear(self) -> None:
        self.data[:] = bytes(self.num_bytes)

    def _check_range(self, index: int) -> None:
        if not (0 <= index < self.num_pieces):
            raise IndexError(
                f"Bit index {index} out of range (0 to {self.num_pieces - 1})"
            )

    def get_pieces_availability(self) -> Iterator[tuple[int, bool]]:
        for byte_index, byte in enumerate(self.data):
            for bit_index in range(8):
                piece_index = byte_index * 8 + bit_index
                if piece_index >= self.num_pieces:
                    return

                mask = 1 << (7 - bit_index)
                is_available = bool(byte & mask)

                yield piece_index, is_available

    def get_missing_pieces(self) -> Iterator[int]:
        return (index for index, is_available in self.get_pieces_availability() if not is_available)

    def get_available_pieces(self) -> Iterator[int]:
        return (index for index, is_available in self.get_pieces_availability() if is_available)

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}("
            f"data={self.data}, "
            f"num_pieces={self.num_pieces}, "
            f"num_bytes={self.num_bytes}"
            ")"
        )