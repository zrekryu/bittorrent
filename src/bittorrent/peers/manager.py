from typing import ClassVar, Final

from .connection import PeerConnection


class PeerManager:
    MAX_CONNECTIONS: ClassVar[Final[int]] = 200

    def __init__(
        self,
        max_connections: int | None = None
    ) -> None:
        self.max_connections = max_connections or self.MAX_CONNECTIONS

        self.peers: dict[bytes, PeerConnection] = {}

    def add_peer(self, peer: PeerConnection) -> None:
        if peer.peer_id in self.peers:
            raise ValueError(f"Peer {peer.peer_id!r} already exists")

        self.peers[peer.peer_id] = peer

    def remove_peer(self, peer_id: bytes) -> None:
        if peer.peer_id not in self.peers:
            raise ValueError(f"Peer {peer.peer_id!r} not found")

        del self.peers[peer_id]

    def get_peer(self, peer_id: bytes) -> PeerConnection:
        try:
            return self.peers[peer_id]
        except KeyError:
            raise ValueError(f"Peer {peer_id!r} not found")
