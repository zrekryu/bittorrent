import ipaddress
import logging
import struct
from typing import ClassVar, Final

from bittorrent.enums import UDPTrackerAction, UDPTrackerEvent
from bittorrent.exceptions import (
    UDPTrackerConnectionIDExpired,
    UDPTrackerError,
    UDPTrackerTimeout,
)
from bittorrent.utils import (
    extract_udp_tracker_addr,
    generate_tracker_key,
    generate_transaction_id,
    ipv4_str_to_int,
    parse_compact_ipv4_peers,
    parse_compact_ipv6_peers,
)

from .responses import (
    UDPTrackerAnnounceResponse,
    UDPTrackerScrapedFile,
    UDPTrackerScrapeResponse,
)
from .udp_tracker_client_protocol import UDPTrackerClientProtocol
from .udp_tracker_client_session import UDPTrackerClientSession

logger = logging.getLogger(__name__)


class UDPTrackerClient:
    PROTOCOL_ID: ClassVar[Final[int]] = 0x41727101980

    TIMEOUT: ClassVar[Final[int]] = 15
    RETRY_BACKOFF_FACTOR: ClassVar[Final[int]] = 2
    MAX_RETRIES: ClassVar[Final[int]] = 0

    NUM_WANT: ClassVar[Final[int]] = -1

    def __init__(
        self,
        announce_url: str,
        protocol_id: int = PROTOCOL_ID,
        connection_id_ttl: int = UDPTrackerClientSession.CONNECTION_ID_TTL,
        timeout: int = TIMEOUT,
        retry_backoff_factor: int = RETRY_BACKOFF_FACTOR,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._announce_url = announce_url
        self.protocol_id = protocol_id
        self.connection_id_ttl = connection_id_ttl
        self.timeout = timeout
        self.retry_backoff_factor = retry_backoff_factor
        self.max_retries = max_retries

        self.session: UDPTrackerClientSession = UDPTrackerClientSession(
            connection_id_ttl=self.connection_id_ttl
        )

        self.remote_addr: tuple[str, int] = extract_udp_tracker_addr(self._announce_url)

        self._protocol: UDPTrackerClientProtocol | None = None

    async def _initialize_protocol(self) -> None:
        if self._protocol is not None:
            raise RuntimeError("UDP Tracker Client Protocol is already initialized")

        self._protocol = await UDPTrackerClientProtocol.from_address(self.remote_addr)

    def calc_timeout(
        self,
        attempt: int,
        timeout: int | None = None,
        retry_backoff_factor: int | None = None,
    ) -> int:
        timeout = timeout or self.timeout
        backoff = retry_backoff_factor or self.retry_backoff_factor
        return timeout * (backoff**attempt)

    @property
    def announce_url(self) -> str:
        return self._announce_url

    async def connect(
        self,
        timeout: int | None = None,
        retry_backoff_factor: int | None = None,
        max_retries: int | None = None,
    ) -> int:
        if self._protocol is None:
            await self._initialize_protocol()
            assert self._protocol is not None

        transaction_id: int = generate_transaction_id()

        datagram: bytes = struct.pack(
            "!QII", self.protocol_id, UDPTrackerAction.CONNECT.value, transaction_id
        )

        for retry in range(1, max(2, (max_retries or self.max_retries) + 1)):
            self._protocol.send_datagram(transaction_id, datagram)

            try:
                action, data, _ = await self._protocol.receive_datagram(
                    transaction_id=transaction_id,
                    timeout=self.calc_timeout(retry, timeout, retry_backoff_factor)
                )
                break
            except UDPTrackerTimeout:
                pass
        else:
            raise UDPTrackerError("Connect response timed out")

        if action == UDPTrackerAction.ERROR:
            raise UDPTrackerError(f"Connect request error: {data[8:].decode('utf-8')}")

        if action != UDPTrackerAction.CONNECT:
            raise UDPTrackerError(
                f"Connect response action mismatch: {action} (expected: {UDPTrackerAction.CONNECT})"
            )

        try:
            connection_id: int = struct.unpack_from("!Q", data, 8)[0]
        except struct.error as exc:
            raise UDPTrackerError(
                f"Failed to unpack connection ID from connect response: {exc}"
            )

        self.session.set_connection_id(connection_id)

        return connection_id

    async def announce(
        self,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        uploaded: int,
        downloaded: int,
        left: int,
        event: UDPTrackerEvent | int | None = 0,
        num_want: int | None = NUM_WANT,
        ip: int | str | None = 0,
        timeout: int | None = None,
        retry_backoff_factor: int | None = None,
        max_retries: int | None = None,
    ) -> UDPTrackerAnnounceResponse:
        if not self.session.has_connection_id():
            raise UDPTrackerError("Client is not connected. call connect() first")

        if self.session.is_connection_expired():
            raise UDPTrackerConnectionIDExpired(
                "Connection ID expired, call connect() to request a new connection"
            )

        assert self._protocol is not None

        transaction_id: int = generate_transaction_id()

        datagram: bytes = struct.pack(
            "!QII20s20sQQQIIIiH",
            self.session.get_connection_id(),
            UDPTrackerAction.ANNOUNCE.value,
            transaction_id,
            info_hash,
            peer_id,
            downloaded,
            left,
            uploaded,
            event,
            ipv4_str_to_int(ip) if isinstance(ip, str) else ip,
            generate_tracker_key(),
            num_want,
            port,
        )

        for retry in range(1, max(2, (max_retries or self.max_retries) + 1)):
            self._protocol.send_datagram(transaction_id, datagram)

            try:
                async with self.session:
                    action, data, addr = await self._protocol.receive_datagram(
                        transaction_id=transaction_id,
                        timeout=self.calc_timeout(retry, timeout, retry_backoff_factor)
                    )
                    break
            except UDPTrackerConnectionIDExpired:
                await self.connect()
            except UDPTrackerTimeout:
                pass
        else:
            raise UDPTrackerError("Announce request timed out")

        if action == UDPTrackerAction.ERROR:
            raise UDPTrackerError(f"Announce request error: {data[8:].decode('utf-8')}")

        if action != UDPTrackerAction.ANNOUNCE:
            raise UDPTrackerError(
                f"Announce response action mismatch: {action} (expected: {UDPTrackerAction.ANNOUNCE})"
            )

        try:
            interval, leechers, seeders = struct.unpack_from("!III", data, 8)
        except struct.error as exc:
            raise UDPTrackerError(
                "Failed to unpack "
                "'interval', 'leechers' and 'seeders' "
                f"from announce response: {exc}"
            )

        raw_peers = memoryview(data)[20:]
        peers: list[tuple[str, int]] = []

        ip_version: int = ipaddress.ip_address(addr[0]).version
        if ip_version == 4:
            try:
                peers = parse_compact_ipv4_peers(raw_peers)
            except ValueError as exc:
                raise UDPTrackerError(
                    f"Failed to parse IPv4 peers from announce response: {exc}"
                )
        elif ip_version == 6:
            try:
                peers = parse_compact_ipv6_peers(raw_peers)
            except ValueError as exc:
                raise UDPTrackerError(
                    f"Failed to parse IPv6 peers from announce response: {exc}"
                )
        else:
            raise UDPTrackerError(
                f"Unsupported IP version for peers in announce response: {ip_version} (address: {addr[0]})"
            )

        return UDPTrackerAnnounceResponse(
            interval=interval, leechers=leechers, seeders=seeders, peers=peers
        )

    async def scrape(
        self,
        info_hashes: list[bytes] | bytes,
        timeout: int | None = None,
        retry_backoff_factor: int | None = None,
        max_retries: int | None = None,
    ) -> UDPTrackerScrapeResponse:
        if self.session.has_connection_id() is None:
            raise UDPTrackerError("Client is not connected. call connect() first")

        if self.session.is_connection_expired():
            raise UDPTrackerConnectionIDExpired(
                "Connection ID expired, call connect() to request a new connection"
            )

        assert self._protocol is not None

        info_hashes = (
            [info_hashes] if not isinstance(info_hashes, list) else info_hashes
        )

        compact_info_hashes = b"".join(info_hashes)

        transaction_id: int = generate_transaction_id()

        datagram = struct.pack(
            f"!QII{len(compact_info_hashes)}s",
            self.session.get_connection_id(),
            UDPTrackerAction.SCRAPE.value,
            transaction_id,
            compact_info_hashes,
        )

        for retry in range(1, max(2, (max_retries or self.max_retries) + 1)):
            self._protocol.send_datagram(transaction_id, datagram)

            try:
                async with self.session:
                    action, data, addr = await self._protocol.receive_datagram(
                        transaction_id=transaction_id,
                        timeout=self.calc_timeout(retry, timeout, retry_backoff_factor)
                    )
                    break
            except UDPTrackerConnectionIDExpired:
                await self.connect()
            except UDPTrackerTimeout:
                pass
        else:
            raise UDPTrackerError("Scrape request timed out")

        if action == UDPTrackerAction.ERROR:
            raise UDPTrackerError(f"Scrape request error: {data[8:].decode('utf-8')}")

        if action != UDPTrackerAction.SCRAPE:
            raise UDPTrackerError(
                f"Scrape response action mismatch: {action} (expected: {UDPTrackerAction.SCRAPE})"
            )

        raw_files = memoryview(data)[8:]
        files: list[UDPTrackerScrapedFile] = []
        for i in range(0, len(raw_files), 12):
            try:
                seeders: int = struct.unpack_from("!I", raw_files, i)[0]
            except struct.error as exc:
                raise UDPTrackerError(
                    f"Failed to unpack field 'seeders' from scrape response: {exc}"
                )
            try:
                completed: int = struct.unpack_from("!I", raw_files, i + 4)[0]
            except struct.error as exc:
                raise UDPTrackerError(
                    f"Failed to unpack field 'completed' from scrape response: {exc}"
                )
            try:
                leechers: int = struct.unpack_from("!I", raw_files, i + 8)[0]
            except struct.error as exc:
                raise UDPTrackerError(
                    f"Failed to unpack field 'leechers' from scrape response: {exc}"
                )

            file = UDPTrackerScrapedFile(
                seeders=seeders, completed=completed, leechers=leechers
            )
            files.append(file)

        return UDPTrackerScrapeResponse(files)

    def close(self) -> None:
        if self._protocol:
            self._protocol.close()
            self._protocol = None

        self.session.close()
