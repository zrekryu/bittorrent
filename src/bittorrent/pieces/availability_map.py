from collections.abc import Iterable


class PieceAvailabilityMap:
    def __init__(self, num_pieces: int) -> None:
        self.num_pieces = num_pieces

        self._piece_peers: list[set[bytes]] = [set() for _ in range(self.num_pieces)]

    def add_peer(self, index: int, peer_id: bytes) -> None:
        self._check_range(index)

        self._piece_peers[index].add(peer_id)

    def remove_peer(self, index: int, peer_id: bytes) -> None:
        self._check_range(index)

        self._piece_peers[index].discard(peer_id)

    def add_peers(self, index: int, peer_ids: Iterable[bytes]) -> None:
        self._check_range(index)

        self._piece_peers[index].update(peer_ids)

    def remove_peers(self, index: int, peer_ids: Iterable[bytes]) -> None:
        self._check_range(index)

        self._piece_peers[index].difference_update(peer_ids)

    def set_peer_pieces(self, peer_id: bytes, pieces_availability: Iterable[tuple[int, bool]]) -> None:
        for index, is_available in pieces_availability:
            if is_available:
                self.add_peer(index, peer_id)
            else:
                self.remove_peer(index, peer_id)

    def get_availability(self, index: int) -> int:
        self._check_range(index)

        return len(self._piece_peers[index])

    def get_peers(self, index: int) -> tuple[bytes, ...]:
        self._check_range(index)

        return tuple(self._piece_peers[index])

    def _check_range(self, index: int) -> None:
        if not 0 <= index < self.num_pieces:
            raise IndexError(
                f"Piece index {index} out of range (0 to {self.num_pieces - 1})"
            )