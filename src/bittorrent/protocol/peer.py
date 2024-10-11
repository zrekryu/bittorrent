import asyncio
import logging
from typing import Self

from ..exceptions import PeerError
from ..enums import PeerStatus

from .handshake import Handshake
from .messages import parse_message, Message, BitField

logger: logging.Logger = logging.getLogger(__name__)

class Peer:
    CONNECT_TIMEOUT: int = 10
    HANDSHAKE_TIMEOUT: int = 10
    CHUNK_SIZE: int = 4096
    
    def __init__(
        self: Self,
        ip: str,
        port: int,
        bitfield: BitField,
        connect_timeout: int = CONNECT_TIMEOUT,
        handshake_timeout: int = HANDSHAKE_TIMEOUT,
        chunk_size: int = CHUNK_SIZE
        ) -> None:
        self.ip = ip
        self.port = port
        
        self.addr_str: str = f"{self.ip}:{self.port}"
        
        self.bitfield: BitField = bitfield
        
        self.connect_timeout = connect_timeout
        self.handshake_timeout = handshake_timeout
        self.chunk_size = chunk_size
        
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        
        self.last_read_time: float = 0.0
        self.last_write_time: float = 0.0
        
        self.handshake: Handshake | None = None
        
        self.status: set[PeerStatus] = {
            PeerStatus.CHOKING,
            PeerStatus.AM_CHOKING
        }
        
        self.requested_block_requests: list[tuple[int, int]] = []
        self.uploaded: int = 0
        self.downloaded: int = 0
    
    def add_status(self: Self, status: PeerStatus) -> None:
        self.status.add(status)
    
    def remove_status(self: Self, status: PeerStatus) -> None:
        self.status.discard(status)
    
    def has_status(self: Self, status: PeerStatus) -> bool:
        return status in self.status
    
    @property
    def is_choking(self: Self) -> bool:
        return self.has_status(PeerStatus.CHOKING)
    
    @is_choking.setter
    def is_choking(self: Self, value: bool) -> None:
        if value:
            self.add_status(PeerStatus.CHOKING)
        else:
            self.remove_status(PeerStatus.CHOKING)
    
    @property
    def is_interested(self: Self) -> bool:
        return self.has_status(PeerStatus.INTERESTED)
    
    @is_interested.setter
    def is_interested(self: Self, value: bool) -> None:
        if value:
            self.add_status(PeerStatus.INTERESTED)
        else:
            self.remove_status(PeerStatus.INTERESTED)
    
    @property
    def am_choking(self: Self) -> bool:
        return self.has_status(PeerStatus.AM_CHOKING)
    
    @am_choking.setter
    def am_choking(self: Self, value: bool) -> None:
        if value:
            self.add_status(PeerStatus.AM_CHOKING)
        else:
            self.remove_status(PeerStatus.AM_CHOKING)
    
    @property
    def am_interested(self: Self) -> bool:
        return self.has_status(PeerStatus.AM_INTERESTED)
    
    @am_interested.setter
    def am_interested(self: Self, value: bool) -> None:
        if value:
            self.add_status(PeerStatus.AM_INTERESTED)
        else:
            self.remove_status(PeerStatus.AM_INTERESTED)
    
    @property
    def is_connected(self: Self) -> bool:
        return self.writer is not None
    
    def _check_connected(self: Self) -> None:
        if not self.is_connected:
            raise RuntimeError(f"Peer is not connected: {self.addr_str}")
    
    async def connect(self: Self) -> None:
        if self.writer:
            raise RuntimeError(f"Peer is already connected:  {self.addr_str}")
        
        try:
            self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(self.ip, self.port), self.connect_timeout)
        except Exception as exc:
            logger.error(f"[{self.addr_str}] - Failed to connect to peer: {type(exc).__name__}: {exc}")
            raise PeerError(f"Failed to connect to peer: {self.addr_str}")
        else:
            logger.info(f"[{self.addr_str}] - Connected to peer.")
    
    async def disconnect(self: Self) -> None:
        self._check_connected()
        
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as exc:
            logger.error(f"[{self.addr_str}] - Unexpected error occurred while disconnecting: {type(exc).__name__}: {exc}")
        finally:
            logger.info(f"[{self.addr_str}] - Disconnected from peer.")
            self.reader, self.writer = None, None
    
    async def _send(self: Self, data: bytes) -> None:
        self._check_connected()
        
        self.writer.write(data)
        await self.writer.drain()
        
        self.last_write_time = asyncio.get_running_loop().time()
    
    async def send_handshake(self: Self, handshake: Handshake) -> None:
        try:
            await self._send(handshake.to_bytes())
        except Exception as exc:
            logger.error(f"[{self.addr_str}] - Failed to send handshake to peer: {exc}")
            raise PeerError(f"[{self.addr_str}] - Failed to send handshake to peer: {exc}")
    
    async def recv_handshake(self: Self) -> bytes:
        try:
            data: bytes = await asyncio.wait_for(self.reader.readexactly(Handshake.LENGTH), timeout=self.handshake_timeout)
            return data
        except asyncio.TimeoutError:
            logger.error(f"[{self.addr_str}] - Peer handshake timed out.")
            raise PeerError(f"Peer handshake timed out: {self.addr_str}")
        except asyncio.IncompleteReadError:
            logger.error(f"[{self.addr_str}] - Peer handshake length is not the expected number of bytes ({handshake.LENGTH}).")
            raise PeerError(f"Peer [{self.addr_str}] handshake length is not the expected number of bytes ({handshake.LENGTH})")
    
    def verify_handshake(self: Self, handshake: Handshake, peer_handshake: Handshake) -> None:
        if peer_handshake.pstr != handshake.pstr:
            logger.error(f"[{self.addr_str}] - Peer handshake protocol string does not match. Received: {peer_handshake.pstr!r}, Expected: {handshake.pstr!r}.")
            raise PeerError(f"Peer [{self.addr_str}] handshake protocol string does not match")
        if peer_handshake.info_hash != handshake.info_hash:
            logger.error(f"[{self.addr_str}] - Peer handshake info hash does not match. Received: {peer_handshake.info_hash!r}, Expected: {handshake.info_hash!r}.")
            raise PeerError(f"Peer [{self.addr_str}] handshake info hash does not match")
    
    async def do_handshake(self: Self, handshake: Handshake) -> None:
        self._check_connected()
        
        # Send the handshake.
        await self.send_handshake(handshake)
        
        # Receive the handshake.
        data: bytes = await self.recv_handshake()
        
        # Verify the received handshake.
        peer_handshake: Handshake = Handshake.from_bytes(data)
        self.verify_handshake(handshake, peer_handshake)
        
        self.handshake = peer_handshake
        logger.debug(f"[{self.addr_str}] - Peer handshake completed successfully.")
    
    @staticmethod
    def decode_message_length_from_bytes(data: bytes) -> int:
        if len(data) < 4:
            raise ValueError("Length of data is less than 4")
        elif len(data) > 4:
            raise ValueError("Length of data is greater than 4")
        
        return int.from_bytes(data, byteorder="big")
    
    @staticmethod
    def decode_message_id_from_bytes(data: bytes) -> int:
        if len(data) < 1:
            raise ValueError("Length of data is less than 1")
        elif len(data) > 1:
            raise ValueError("Length of data is greater than 1")
        
        return int.from_bytes(data, byteorder="big")
    
    async def read_message(self: Self) -> Message:
        self._check_connected()
        
        try:
            length_bytes: bytes = await self.reader.readexactly(4)
        except asyncio.IncompleteReadError:
            logger.error(f"[{self.addr_str}] - Message length is not exactly 4 bytes.")
            raise PeerError(f"Peer [{self.addr_str}] message length is not exactly 4 bytes")
    
        try:
            message_length: int = self.decode_message_length_from_bytes(length_bytes)
        except ValueError as exc:
            logger.error(f"[{self.addr_str}] - Unable to decode message length: {exc}.")
            raise PeerError(f"Unable to decode message length: [{self.addr_str}] - {exc}")
        
        data: bytes = b""
        while len(data) < message_length:
            chunk_size: int = min(self.chunk_size, message_length - len(data))
            chunk: bytes = await self.reader.read(chunk_size)
            
            if not chunk:
                raise PeerError(f"Peer [{self.addr_str}] sent incomplete message body: {len(data)} (expected: {message_length})")
            
            data += chunk
        
        self.last_read_time = asyncio.get_running_loop().time()
        
        data_length: int = len(data)
        message_id: int | None = None
        payload: bytes | None = None
        if data_length > 0:
            message_id = self.decode_message_id_from_bytes(data[:1])
            
            if data_length > 1:
                payload = data[1:]
        
        return parse_message(message_length, message_id, payload)
    
    async def send_message(self: Self, message: Message) -> None:
        try:
            await self._send(message.to_bytes())
        except Exception as exc:
            logger.error(f"[{self.addr_str}] - Failed to send message: {exc}.")
            raise PeerError(f"Failed to send message to peer [{self.addr_str}]: {exc}")
    
    def __repr__(self: Self) -> str:
        return f"Peer(ip={self.ip}, port={self.port})"