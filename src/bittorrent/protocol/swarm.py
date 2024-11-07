import asyncio
import logging
from typing import Generator, Self

from ..exceptions import PeerError
from ..pieces.piece import Piece
from ..pieces.block import Block
from ..pieces.piece_manager import PieceManager

from .peer import Peer
from .peer_address import PeerAddress
from .messages import (
    Message,
    KeepAliveMessage,
    ChokeMessage, UnchokeMessage,
    InterestedMessage, NotInterestedMessage,
    HaveMessage, BitFieldMessage, RequestMessage
    )

logger: logging.Logger = logging.getLogger(__name__)

class Swarm:
    MAX_CONNECTIONS: int = 200
    KEEP_ALIVE_INTERVAL: int = 60
    INACTIVITY_TIMEOUT: int = 120
    SEND_ALREADY_HAVE_PIECE: bool = True
    
    def __init__(
        self: Self,
        bitfield: BitFieldMessage,
        piece_manager: PieceManager,
        connect_timeout: int = Peer.CONNECT_TIMEOUT,
        handshake_timeout: int = Peer.HANDSHAKE_TIMEOUT,
        chunk_size: int = Peer.CHUNK_SIZE,
        max_connections: int = MAX_CONNECTIONS,
        keep_alive_interval: int | None = KEEP_ALIVE_INTERVAL,
        inactivity_timeout: int | None = INACTIVITY_TIMEOUT,
        send_already_have_piece: bool = SEND_ALREADY_HAVE_PIECE
        ) -> None:
        self.bitfield = bitfield
        self.piece_manager = piece_manager
        self.connect_timeout = connect_timeout
        self.handshake_timeout = handshake_timeout
        self.chunk_size = chunk_size
        
        self.max_connections = max_connections
        self.keep_alive_interval = keep_alive_interval
        self.inactivity_timeout = inactivity_timeout
        
        self.send_already_have_piece = send_already_have_piece
        
        self.peers: list[Peer] = []
        
        self._peer_queues: list[asyncio.Queue] = []
        self._peer_message_queues: list[asyncio.Queue] = []
        
        self._peer_message_reading_tasks: dict[Peer, asyncio.Task] = {}
        self._peer_keep_alive_timeout_tasks: dict[Peer, asyncio.Task] = {}
        self._peer_keep_alive_interval_tasks: dict[Peer, asyncio.Task] = {}
    
    async def broadcast_peer(self: Self, peer: Peer) -> None:
        await asyncio.gather(*(queue.put(peer) for queue in self._peer_queues))
    
    async def broadcast_peer_message(self: Self, peer: Peer, message: Message) -> None:
        await asyncio.gather(*(queue.put((peer, message)) for queue in self._peer_message_queues))
    
    async def broadcast_peer_messages(self: Self, peer: Peer) -> None:
        while peer.is_connected:
            try:
                message: Message = await peer.read_message()
            except PeerError as exc:
                logger.error(f"[{peer.addr_str}] - Failed to read peer message: {exc}.")
                await self.remove_peer(peer)
                break
            
            self.handle_messages(peer, message)
            
            await self.broadcast_peer_message(peer, message)
    
    def handle_messages(self: Self, peer: Peer, message: Message) -> None:
        match message:
            case KeepAliveMessage():
                self.handle_keep_alive_message(peer)
            case ChokeMessage():
                self.handle_choke_message(peer)
            case UnchokeMessage():
                self.handle_unchoke_message(peer)
            case InterestedMessage():
                self.handle_interested_message(peer)
            case NotInterestedMessage():
                self.handle_not_interested_message(peer)
            case HaveMessage():
                self.handle_have_message(peer, message)
            case BitFieldMessage():
                self.handle_bitfield_message(peer, message)
            case _:
                pass
    
    def handle_keep_alive_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received Keep-Alive message.")
    
    def handle_choke_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received choke message.")
        
        peer.is_choking = True
    
    def handle_unchoke_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received unchoke message.")
        
        peer.is_choking = False
    
    def handle_interested_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received interested message.")
        
        peer.is_interested = True
    
    def handle_not_interested_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received not interested message.")
        
        peer.is_interested = False
    
    def handle_have_message(self: Self, peer: Peer, have_msg: HaveMessage) -> None:
        logger.debug(f"[{peer.addr_str}] - Received have message: {have_msg.index}.")
        
        try:
            peer.bitfield.set_piece(have_msg.index)
        except IndexError:
            logger.debug(f"[{peer.addr_str}] - Received have message with invalid piece index: {have_msg.index}.")
        
        self.piece_manager.increment_piece_availability_count(have_msg.index)
    
    def handle_bitfield_message(self: Self, peer: Peer, bitfield_msg: BitFieldMessage) -> None:
        logger.debug(f"[{peer.addr_str}] - Received bitfield message.")
        
        bitfield_length: int = len(bitfield_msg.data)
        expected_length: int = (len(self.piece_manager.pieces) + 7) // 8
        if bitfield_length != expected_length:
            logger.error(f"[{peer.addr_str}] - Received bitfield message with invalid length: {bitfield_length} (expected: {expected_length}).")
            return
        
        peer.bitfield = bitfield_msg
        self.piece_manager.update_pieces_availability_counter_with_bitfield(bitfield_msg)
    
    async def send_keep_alive_periodically(self: Self, peer: Peer) -> None:
        while peer.is_connected:
            elapsed_time: float = asyncio.get_running_loop().time() - peer.last_write_time
            remaining_time: float = self.keep_alive_interval - elapsed_time
            
            if remaining_time <= 0.0:
                try:
                    await peer.send_keep_alive_message()
                except PeerError:
                    await self.remove_peer(peer)
                    break
                else:
                    logger.debug(f"[{peer.addr_str}] - Sent a Keep-Alive message to the peer.")
                    await asyncio.sleep(self.keep_alive_interval)
            else:
                await asyncio.sleep(remaining_time)
    
    async def monitor_inactivity(self: Self, peer: Peer) -> None:
        while peer.is_connected:
            inactivity_duration: float = asyncio.get_running_loop().time() - peer.last_read_time
            remaining_time: float = self.inactivity_timeout - inactivity_duration
            
            if remaining_time <= 0.0:
                logger.debug(f"[{peer.addr_str}] - Peer inactivity timeout. Disconnecting peer.")
                await self.remove_peer(peer)
                break
            
            await asyncio.sleep(remaining_time)
    
    def add_peer_queue(self: Self, queue: asyncio.Queue) -> None:
        if queue in self._peer_queues:
            raise ValueError("Queue already exists")
        
        self._peer_queues.append(queue)
    
    def remove_peer_queue(self: Self, queue: asyncio.Queue) -> None:
        try:
            self._peer_queues.remove(queue)
        except ValueError:
            raise ValueError("Queue does not exists")
    
    def add_peer_message_queue(self: Self, queue: asyncio.Queue) -> None:
        if queue in self._peer_queues:
            raise ValueError("Queue already exists")
        
        self._peer_message_queues.append(queue)
    
    def remove_peer_message_queue(self: Self, queue: asyncio.Queue) -> None:
        try:
            self._peer_message_queues.remove(queue)
        except ValueError:
            raise ValueError("Queue does not exists")
    
    def start_peer_message_reading(self: Self, peer: Peer) -> None:
        if peer in self._peer_message_reading_tasks:
            raise KeyError("Peer message reading was already started")
        
        self._peer_message_reading_tasks[peer] = asyncio.create_task(self.broadcast_peer_messages(peer))
    
    async def stop_peer_message_reading(self: Self, peer: Peer) -> None:
        if peer not in self._peer_message_reading_tasks:
            raise KeyError("Peer message reading was not started")
        
        task = self._peer_message_reading_tasks[peer]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    def enable_peer_inactivity_timeout(self: Self, peer: Peer) -> None:
        if self.inactivity_timeout is None:
            raise ValueError("inactivity_timeout is None.")
        if peer in self._peer_keep_alive_timeout_tasks:
            raise ValueError("Peer already has a keep-alive timeout.")
        
        self._peer_keep_alive_timeout_tasks[peer] = asyncio.create_task(
            self.monitor_inactivity(peer)
        )
    
    async def disable_peer_inactivity_timeout(self: Self, peer: Peer) -> None:
        task = self._peer_keep_alive_timeout_tasks.pop(peer, None)
        if task is None:
            raise ValueError("Peer inactivity timeout not enabled.")
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    def enable_peer_keep_alive_interval(self: Self, peer: Peer) -> None:
        if self.keep_alive_interval is None:
            raise ValueError("keep_alive_interval is None.")
        if peer in self._peer_keep_alive_interval_tasks:
            raise ValueError("Peer already has a keep-alive interval.")
        
        self._peer_keep_alive_interval_tasks[peer] = asyncio.create_task(
            self.send_keep_alive_periodically(peer)
        )
    
    async def disable_peer_keep_alive_interval(self: Self, peer: Peer) -> None:
        task = self._peer_keep_alive_interval_tasks.pop(peer, None)
        if task is None:
            raise ValueError("Peer keep-alive interval not enabled.")
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    async def connect_peer(self: Self, peer_addr: PeerAddress) -> Peer:
        if len(self.peers) >= self.max_connections:
            raise RuntimeError(f"Max peer connections exceeded ({self.max_connections})")
        
        peer: Peer = Peer(
            host=peer_addr.host,
            port=peer_addr.port,
            bitfield=self.bitfield,
            connect_timeout=self.connect_timeout,
            handshake_timeout=self.handshake_timeout,
            chunk_size=self.chunk_size
            )
        await peer.connect()
        
        return peer
    
    async def disconnect_peer(self: Self, peer: Peer) -> None:
        if peer in self._peer_message_reading_tasks:
            await self.stop_peer_message_reading(peer)
        if peer in self._peer_keep_alive_timeout_tasks:
            await self.disable_peer_inactivity_timeout(peer)
        if peer in self._peer_keep_alive_interval_tasks:
            await self.disable_peer_keep_alive_interval(peer)
        
        await peer.disconnect()
    
    async def disconnect_peers(self: Self) -> list[Peer | PeerError]:
        return await asyncio.gather(*(self.disconnect_peer(peer) for peer in self.peers), return_exceptions=True)
    
    async def add_peer(self: Self, peer_addr: PeerAddress) -> Peer:
        peer: Peer = await self.connect_peer(peer_addr)
        
        self.peers.append(peer)
        await self.broadcast_peer(peer)
        
        return peer
    
    async def add_peers(self: Self, peer_addresses: list[PeerAddress]) -> list[Peer | tuple[PeerAddress, PeerError]]:
        async def add_peer(peer_addr: PeerAddress) -> Peer | tuple[PeerAddress, PeerError]:
            try:
                peer: Peer = await self.add_peer(peer_addr)
            except PeerError as exc:
                return (peer_addr, exc)
            else:
                return peer
        
        return await asyncio.gather(*(add_peer(peer_addr) for peer_addr in peer_addresses))
    
    async def remove_peer(self: Self, peer: Peer) -> None:
        if peer not in self.peers:
            raise KeyError(f"Peer does not exists: {peer}")
        
        try:
            await self.disconnect_peer(peer)
        except Exception as exc:
            logger.debug(f"[{peer.addr_str}] - Failed to disconnect from peer: {exc}.")
        finally:
            self.peers.remove(peer)
    
    async def remove_peers(self: Self, peers: list[Peer]) -> list[Peer | tuple[Peer, PeerError]]:
        async def remove_peer(peer: Peer) -> Peer | tuple[Peer, PeerError]:
            try:
                await self.remove_peer(peer)
            except PeerError as exc:
                return (peer, exc)
            else:
                return peer
        
        return await asyncio.gather(*(remove_peer(peer) for peer in peers))
    
    def has_unchoked_peer(self: Self) -> bool:
        return any(not peer.is_choking for peer in self.peers)
    
    def get_peers(
        self: Self,
        exclude_peers: Peer | list[Peer] | None = None,
        unchoked: bool | None = None,
        can_accept_more_incoming_block_requests: bool | None = None,
        can_accept_more_outgoing_block_requests: bool | None = None,
        include_incoming_block_requests: tuple[Piece, Block] | list[tuple[Piece, Block]] | None = None,
        include_outgoing_block_requests: tuple[Piece, Block] | list[tuple[Piece, Block]] | None = None,
        exclude_incoming_block_requests: tuple[Piece, Block] | list[tuple[Piece, Block]] | None = None,
        exclude_outgoing_block_requests: tuple[Piece, Block] | list[tuple[Piece, Block]] | None = None,
        has_pieces: int | tuple[int] | None = None,
        missing_pieces: int | tuple[int] | None = None,
        limit: int = 200
        ) -> Generator[Peer, None, None]:
        for peer in self.peers:
            if exclude_peers is not None:
                peers: list[Peer] = [exclude_peers] if isinstance(exclude_peers, Peer) else exclude_peers
                if peer in peers:
                    continue
            
            if unchoked is not None:
                is_choking: bool = peer.is_choking
                if unchoked and is_choking:
                    continue
                if not unchoked and not is_choking:
                    continue
            
            if can_accept_more_incoming_block_requests is not None:
                accept: bool = peer.can_accept_more_incoming_block_requests()
                if can_accept_more_incoming_block_requests and not accept:
                    continue
                if not can_accept_more_incoming_block_requests and accept:
                    continue
            
            if can_accept_more_outgoing_block_requests is not None:
                accept: bool = peer.can_accept_more_outgoing_block_requests()
                if can_accept_more_outgoing_block_requests and not accept:
                    continue
                if not can_accept_more_outgoing_block_requests and accept:
                    continue
            
            if include_incoming_block_requests is not None:
                block_requests: list[tuple[Piece, Block]] = [include_incoming_block_requests] if not isinstance(include_incoming_block_requests, list) else include_incoming_block_requests
                if not all(block_req in peer.incoming_block_requests for block_req in block_requests):
                    continue
            
            if include_outgoing_block_requests is not None:
                block_requests: list[tuple[Piece, Block]] = [include_outgoing_block_requests] if not isinstance(include_outgoing_block_requests, list) else include_outgoing_block_requests
                if not all(block_req in peer.outgoing_block_requests for block_req in block_requests):
                    continue
            
            if exclude_incoming_block_requests is not None:
                block_requests: list[tuple[Piece, Block]] = [exclude_incoming_block_requests] if not isinstance(exclude_incoming_block_requests, list) else exclude_incoming_block_requests
                if all(block_req in peer.incoming_block_requests for block_req in block_requests):
                    continue
            
            if exclude_outgoing_block_requests is not None:
                block_requests: list[tuple[Piece, Block]] = [exclude_outgoing_block_requests] if not isinstance(exclude_outgoing_block_requests, list) else exclude_outgoing_block_requests
                if all(block_req in peer.outgoing_block_requests for block_req in block_requests):
                    continue
            
            if has_pieces is not None:
                pieces: tuple[int] = [has_pieces] if not isinstance(has_pieces, tuple) else has_pieces
                if not all(peer.bitfield.has_piece(piece) for piece in pieces):
                    continue
            
            if missing_pieces is not None:
                pieces: tuple[int] = [missing_pieces] if not isinstance(missing_pieces, tuple) else missing_pieces
                if not all(not peer.bitfield.has_piece(piece) for piece in pieces):
                    continue
            
            yield peer
            return
    
    async def broadcast_have_piece(self: Self, index: int) -> tuple[list[Peer], list[tuple[Peer, PeerError]]]:
        succeeded_peers: list[Peer] = []
        failed_peers: list[tuple[Peer, PeerError]] = []
        
        async def send(peer: Peer) -> None:
            try:
                await peer.send_have_message(index)
            except PeerError as exc:
                await self.disconnect_peer(peer)
                failed_peers.append((peer, exc))
            else:
                succeeded_peers.append(peer)
        
        tasks: Generator[asyncio.Task, None, None] = (
            asyncio.create_task(send(peer))
            for peer in self.get_peers(
                unchoked=True,
                missing_pieces=index if not self.send_already_have_piece else None
                )
            )
        await asyncio.gather(*tasks)
        
        return (succeeded_peers, failed_peers)
    
    async def close(self: Self) -> None:
        await self.remove_peers(self.peers)