import asyncio
import logging
import math
from typing import Self

from ..exceptions import PeerError
from ..pieces.piece_manager import PieceManager

from .peer import Peer
from .messages import (
    Message,
    KeepAlive,
    Choke, Unchoke,
    Interested, NotInterested,
    Have, BitField, Request
    )

logger: logging.Logger = logging.getLogger(__name__)

class Swarm:
    MAX_CONNECTIONS: int = 200
    KEEP_ALIVE_INTERVAL: int = 60
    KEEP_ALIVE_TIMEOUT: int = 120
    SEND_REDUNDANT_HAVE: bool = True
    
    def __init__(
        self: Self,
        bitfield: BitField,
        piece_manager: PieceManager,
        connect_timeout: int = Peer.CONNECT_TIMEOUT,
        handshake_timeout: int = Peer.HANDSHAKE_TIMEOUT,
        chunk_size: int = Peer.CHUNK_SIZE,
        max_connections: int = MAX_CONNECTIONS,
        keep_alive_interval: int = KEEP_ALIVE_INTERVAL,
        keep_alive_timeout: int = KEEP_ALIVE_TIMEOUT,
        send_redundant_have: bool = SEND_REDUNDANT_HAVE
        ) -> None:
        self.bitfield = bitfield
        self.piece_manager = piece_manager
        self.connect_timeout = connect_timeout
        self.handshake_timeout = handshake_timeout
        self.chunk_size = chunk_size
        
        self.max_connections = max_connections
        self.keep_alive_interval = keep_alive_interval
        self.keep_alive_timeout = keep_alive_timeout
        
        self.peers: list[Peer] = []
        
        self.__peer_queues: list[asyncio.Queue] = []
        self.__peer_message_queues: list[asyncio.Queue] = []
        
        self.__peer_message_reading_tasks: dict[Peer, asyncio.Task] = {}
        self.__peer_keep_alive_tasks: dict[Peer, asyncio.Task] = {}
        self.__peer_monitor_inactivity_tasks: dict[Peer, asyncio.Task] = {}
        
        self.__peer_add_event: asyncio.Event = asyncio.Event()
        self.__peer_unchoke_event: asyncio.Event = asyncio.Event()
    
    async def __broadcast_peer(self: Self, peer: Peer) -> None:
        await asyncio.gather(*(queue.put(peer) for queue in self.__peer_queues))
    
    async def ___broadcast_peer_message(self: Self, peer_message: tuple[Peer, Message]) -> None:
        await asyncio.gather(*(queue.put(peer_message) for queue in self.__peer_message_queues))
    
    async def __broadcast_peer_messages(self: Self, peer: Peer) -> None:
        while peer.is_connected:
            message: Message = await peer.read_message()
            self.__handle_messages(peer, message)
            
            await self.___broadcast_peer_message((peer, message))
    
    def __handle_messages(self: Self, peer: Peer, message: Message) -> None:
        match message:
            case Choke():
                self.__handle_choke_message(peer)
            case Unchoke():
                self.__handle_unchoke_message(peer)
            case Interested():
                self.__handle_interested_message(peer)
            case NotInterested():
                self.__handle_not_interested_message(peer)
            case Have():
                self.__handle_have_message(peer, message)
            case BitField():
                self.__handle_bitfield_message(peer, message)
            case _:
                pass
    
    def __handle_choke_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received choke message.")
        
        peer.is_choking = True
    
    def __handle_unchoke_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received unchoke message.")
        
        peer.is_choking = False
        
        self.__peer_unchoke_event.set()
    
    def __handle_interested_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received interested message.")
        
        peer.is_interested = True
    
    def __handle_not_interested_message(self: Self, peer: Peer) -> None:
        logger.debug(f"[{peer.addr_str}] - Received not interested message.")
        
        peer.is_interested = False
    
    def __handle_have_message(self: Self, peer: Peer, have_msg: Have) -> None:
        logger.debug(f"[{peer.addr_str}] - Received have message.")
        
        try:
            peer.bitfield.set_piece(have_msg.index)
        except IndexError:
            logger.debug(f"[{peer.addr_str}] - Received have message with invalid piece index: {have_msg.index}.")
    
    def __handle_bitfield_message(self: Self, peer: Peer, bitfield_msg: BitField) -> None:
        logger.debug(f"[{peer.addr_str}] - Received bitfield message.")
        
        bitfield_length: int = len(bitfield_msg.data)
        expected_length: int = math.ceil(len(self.piece_manager.pieces) / 8)
        if bitfield_length != expected_length:
            logger.error(f"[{peer.addr_str}] - Received bitfield with invalid length: {bitfield_length} (expected: {expected_length}).")
            return
        
        peer.bitfield = bitfield_msg
        self.piece_manager.update_pieces_availability_counter_with_bitfield(bitfield_msg)
    
    async def __send_keep_alive_periodically(self: Self, peer: Peer) -> None:
        while peer.is_connected:
            elapsed_time: int = asyncio.get_running_loop().time() - peer.last_write_time
            remaining_time: int = self.keep_alive_interval - elapsed_time
            
            if remaining_time <= 0:
                try:
                    await peer.send_keep_alive_message()
                except PeerError:
                    await self.disconnect_peer(peer)
                else:
                    logger.debug(f"[{peer.addr_str}] - Sent a Keep-Alive message to the peer.")
                    await asyncio.sleep(self.keep_alive_interval)
            else:
                await asyncio.sleep(remaining_time)
    
    async def __monitor_inactivity(self: Self, peer: Peer) -> None:
        while peer.is_connected:
            inactivity_duration: int = asyncio.get_running_loop().time() - peer.last_read_time
            remaining_time: int = self.keep_alive_timeout - inactivity_duration
            
            if remaining_time <= 0:
                logger.debug(f"[{peer.addr_str}] - Peer inactivity timeout. Disconnecting peer.")
                await self.disconnect_peer(peer)
                break
            
            await asyncio.sleep(remaining_time)
    
    def add_peer_queue(self: Self, queue: asyncio.Queue) -> None:
        self.__peer_queues.append(queue)
    
    def remove_peer_queue(self: Self, queue: asyncio.Queue) -> None:
        self.__peer_queues.remove(queue)
    
    def add_peer_message_queue(self: Self, queue: asyncio.Queue) -> None:
        self.__peer_message_queues.append(queue)
    
    def remove_peer_message_queue(self: Self, queue: asyncio.Queue) -> None:
        self.__peer_message_queues.remove(queue)
    
    def start_peer_message_reading(self: Self, peer: Peer) -> None:
        self.__peer_message_reading_tasks[peer] = asyncio.create_task(self.__broadcast_peer_messages(peer))
    
    async def stop_peer_message_reading(self: Self, peer: Peer) -> None:
        self.__peer_message_reading_tasks[peer].cancel()
        await asyncio.wait({self.__peer_message_reading_tasks[peer]})
    
    def start_peer_periodic_keep_alive(self: Self, peer: Peer) -> None:
        self.__peer_keep_alive_tasks[peer] = asyncio.create_task(self.__send_keep_alive_periodically(peer))
    
    async def stop_peer_periodic_keep_alive(self: Self, peer: Peer) -> None:
        self.__peer_keep_alive_tasks[peer].cancel()
        await asyncio.wait({self.__peer_keep_alive_tasks[peer]})
    
    def start_peer_inactivity_monitor(self: Self, peer: Peer) -> None:
        self.__peer_monitor_inactivity_tasks[peer] = asyncio.create_task(self.__monitor_inactivity(peer))
    
    async def stop_peer_inactivity_monitor(self: Self, peer: Peer) -> None:
        self.__peer_monitor_inactivity_tasks[peer].cancel()
        await asyncio.wait({self.__peer_monitor_inactivity_tasks[peer]})
    
    async def connect_peer(self: Self, peer_info: tuple[str, int]) -> Peer:
        if len(self.peers) >= self.max_connections:
            raise RuntimeError(f"Max peer connections exceeded ({self.max_connections})")
        
        peer: Peer = Peer(
            ip=peer_info[0],
            port=peer_info[1],
            bitfield=self.bitfield,
            connect_timeout=self.connect_timeout,
            handshake_timeout=self.handshake_timeout,
            chunk_size=self.chunk_size
            )
        await peer.connect()
        
        self.peers.append(peer)
        await self.__broadcast_peer(peer)
        self.__peer_add_event.set()
        
        return peer
    
    async def disconnect_peer(self: Self, peer: Peer) -> None:
        if peer in self.__peer_message_reading_tasks:
            await self.stop_peer_message_reading(peer)
        if peer in self.__peer_keep_alive_tasks:
            await self.stop_peer_periodic_keep_alive(peer)
        if peer in self.__peer_monitor_inactivity_tasks:
            await self.stop_peer_inactivity_monitor(peer)
        
        try:
            await peer.disconnect()
        finally:
            self.peers.remove(peer)
    
    async def disconnect_peers(self: Self) -> None:
        await asyncio.gather(*(self.disconnect_peer(peer) for peer in self.peers))
    
    async def add_peers(self: Self, peers_info: list[tuple[str, int]], return_exceptions: bool = True) -> list[Peer | PeerError]:
        return await asyncio.gather(*(self.connect_peer(peer_info) for peer_info in peers_info), return_exceptions=return_exceptions)
    
    def has_unchoked_peers(self: Self) -> bool:
        return any(True for peer in self.peers if not peer.is_choking)
    
    def get_unchoked_peers(self: Self) -> list[Peer]:
        return [peer for peer in self.peers if not peer.is_choking]
    
    async def await_peer_add_event(self: Self) -> None:
        self.__peer_add_event.clear()
        await self.__peer_add_event.wait()
    
    async def await_peer_unchoke_event(self: Self) -> None:
        self.__peer_unchoke_event.clear()
        await self.__peer_unchoke_event.wait()
    
    async def broadcast_have_piece(self: Self, index: int) -> None:
        for peer in self.piece_manager.get_unchoked_peers():
            if peer.bitfield.has_piece(index) and not self.send_redundant_have:
                continue
            
            await peer.send_have_message(index)