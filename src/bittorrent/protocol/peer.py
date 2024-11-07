import asyncio
import logging
from typing import Self

from ..exceptions import PeerError
from ..enums import PeerStatus

from ..pieces.piece import Piece
from ..pieces.block import Block

from .peer_address import PeerAddress
from .handshake import Handshake
from .messages import (
    parse_message,
    Message,
    KeepAliveMessage,
    ChokeMessage, UnchokeMessage,
    HaveMessage, BitFieldMessage,
    InterestedMessage, NotInterestedMessage,
    RequestMessage, PieceMessage, CancelMessage,
    PortMessage
    )

logger: logging.Logger = logging.getLogger(__name__)

class Peer:
    CONNECT_TIMEOUT: int = 10
    HANDSHAKE_TIMEOUT: int = 10
    CHUNK_SIZE: int = 4096
    
    MAX_INCOMING_BLOCK_REQUESTS: int = 10
    MAX_OUTGOING_BLOCK_REQUESTS: int = 10
    
    def __init__(
        self: Self,
        host: str,
        port: int,
        bitfield: BitFieldMessage,
        connect_timeout: int = CONNECT_TIMEOUT,
        handshake_timeout: int = HANDSHAKE_TIMEOUT,
        chunk_size: int = CHUNK_SIZE,
        max_incoming_block_requests: int = MAX_INCOMING_BLOCK_REQUESTS,
        max_outgoing_block_requests: int = MAX_OUTGOING_BLOCK_REQUESTS
        ) -> None:
        self.host = host
        self.port = port
        
        self.addr_str: str = f"{self.host}:{self.port}"
        
        self.bitfield: BitFieldMessage = bitfield
        
        self.connect_timeout = connect_timeout
        self.handshake_timeout = handshake_timeout
        self.chunk_size = chunk_size
        
        self.max_incoming_block_requests = max_incoming_block_requests
        self.max_outgoing_block_requests = max_outgoing_block_requests
        
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        
        self.last_read_time: float = 0.0
        self.last_write_time: float = 0.0
        
        self.handshake: Handshake | None = None
        
        self.status: set[PeerStatus] = {
            PeerStatus.CHOKING,
            PeerStatus.AM_CHOKING
        }
        
        self.incoming_block_requests: list[tuple[Piece, Block]] = []
        self.outgoing_block_requests: list[tuple[Piece, Block]] = []
        
        self.uploaded: int = 0
        self.downloaded: int = 0
    
    @property
    def peer_address(self: Self) -> PeerAddress:
        return PeerAddress(self.host, self.port)
    
    @property
    def has_handshaken(self: Self) -> bool:
        return self.handshake is not None
    
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
    
    def can_accept_more_incoming_block_requests(self: Self):
        return len(self.incoming_block_requests) < self.max_incoming_block_requests
    
    def can_accept_more_outgoing_block_requests(self: Self):
        return len(self.outgoing_block_requests) < self.max_outgoing_block_requests
    
    def update_uploaded(self: Self, length: int) -> None:
        if length < 0:
            raise ValueError(f"Negative uploaded length is not allowed: {length}")
        
        self.uploaded += length
    
    def update_downloaded(self: Self, length: int) -> None:
        if length < 0:
            raise ValueError(f"Negative downloaded length is not allowed: {length}")
        
        self.downloaded += length
    
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
            self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), timeout=self.connect_timeout)
        except asyncio.TimeoutError as exc:
            logger.error(f"[{self.addr_str}] - Failed to connect to peer due to timeout.")
            raise PeerError(f"Failed to connect to peer due to timeout: {self.addr_str}")
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
            raise PeerError(f"Failed to disconnect from peer: {self.addr_str}")
        else:
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
            logger.error(f"[{self.addr_str}] - Peer handshake length is not the expected number of bytes ({Handshake.LENGTH}).")
            raise PeerError(f"Peer [{self.addr_str}] handshake length is not the expected number of bytes ({Handshake.LENGTH})")
    
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
        peer_handshake: Handshake = Handshake.from_bytes(data)
        
        # Verify the received handshake.
        self.verify_handshake(handshake, peer_handshake)
        
        # Set the peer's handshake.
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
        
        # Read message length.
        try:
            length_bytes: bytes = await self.reader.readexactly(4)
        except asyncio.IncompleteReadError:
            logger.error(f"[{self.addr_str}] - Message length is not exactly 4 bytes.")
            raise PeerError(f"Peer [{self.addr_str}] message length is not exactly 4 bytes")
        
        # Read message length.
        try:
            message_length: int = self.decode_message_length_from_bytes(length_bytes)
        except ValueError as exc:
            logger.error(f"[{self.addr_str}] - Unable to decode message length: {exc}.")
            raise PeerError(f"Unable to decode message length: [{self.addr_str}] - {exc}")
        
        # Read message payload.
        data: bytes = b""
        while len(data) < message_length:
            chunk_size: int = min(self.chunk_size, message_length - len(data))
            chunk: bytes = await self.reader.read(chunk_size)
            
            if not chunk:
                logger.error(f"[{self.addr_str}] - Peer sent incomplete message body: {len(data)} (expected: {message_length}).")
                raise PeerError(f"Peer [{self.addr_str}] sent incomplete message body: {len(data)} (expected: {message_length})")
            
            data += chunk
        
        self.last_read_time = asyncio.get_running_loop().time()
        
        # Extract message ID and payload.
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
    
    async def send_keep_alive_message(self: Self) -> None:
        await self.send_message(KeepAliveMessage())
    
    async def send_choke_message(self: Self) -> None:
        await self.send_message(ChokeMessage())
    
    async def send_unchoke_message(self: Self) -> None:
        await self.send_message(UnchokeMessage())
    
    async def send_interested_message(self: Self) -> None:
        await self.send_message(InterestedMessage())
    
    async def send_not_interested_message(self: Self) -> None:
        await self.send_message(NotInterestedMessage())
    
    async def send_have_message(self: Self, index: int) -> None:
        await self.send_message(HaveMessage(index))
    
    async def send_bitfield_message(self: Self, data: bytes) -> None:
        await self.send_message(BitFieldMessage(data))
    
    async def send_request_message(self: Self, index: int, begin: int, length: int) -> None:
        await self.send_message(RequestMessage(index, begin, length))
    
    async def send_piece_message(self: Self, index: int, begin: int, piece: bytes) -> None:
        await self.send_message(PieceMessage(index, begin, piece))
    
    async def send_cancel_message(self: Self, index: int, begin: int, length: int) -> None:
        await self.send_message(CancelMessage(index, begin, length))
    
    async def send_port_message(self: Self, listen_port: int) -> None:
        await self.send_message(PortMessage(listen_port))
    
    def __repr__(self: Self) -> str:
        return (
            f"Peer("
            f"host={self.host}, "
            f"port={self.port}, "
            f"has_handshaken={self.has_handshaken}, "
            f"is_connected={self.is_connected}, "
            f"is_choking={self.is_choking}, "
            f"is_interested={self.is_interested}"
            ")"
            )