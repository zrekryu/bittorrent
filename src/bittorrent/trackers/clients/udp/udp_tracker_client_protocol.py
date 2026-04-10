from __future__ import annotations

import asyncio
import logging
import struct
from typing import cast

from bittorrent.enums import UDPTrackerAction
from bittorrent.exceptions import UDPTrackerTimeout

logger = logging.getLogger(__name__)

type UDPTrackerDatagram = tuple[UDPTrackerAction | int, bytes, tuple[str, int]]


class UDPTrackerClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self._transport: asyncio.DatagramTransport | None = None
        self._pending_requests: dict[int, asyncio.Future[UDPTrackerDatagram]] = {}

    @classmethod
    async def from_address(cls, remote_addr: tuple[str, int]) -> UDPTrackerClientProtocol:
        loop = asyncio.get_running_loop()
        _, protocol = await loop.create_datagram_endpoint(
            lambda: cls(), remote_addr=remote_addr
        )
        return protocol

    def create_request(self, transaction_id: int) -> None:
        self._pending_requests[transaction_id] = (
            asyncio.get_running_loop().create_future()
        )

    def delete_request(self, transaction_id: int) -> None:
        self._pending_requests.pop(transaction_id, None)

    def get_pending_request(
        self, transaction_id: int
    ) -> asyncio.Future[UDPTrackerDatagram]:
        future: asyncio.Future[UDPTrackerDatagram] | None = self._pending_requests.get(
            transaction_id
        )
        if future is None:
            raise KeyError(f"Pending request not found: {transaction_id}")

        return future

    def set_response_to_request(
        self,
        transaction_id: int,
        action: UDPTrackerAction | int,
        data: bytes,
        addr: tuple[str, int],
    ) -> None:
        future = self.get_pending_request(transaction_id)
        future.set_result((action, data, addr))

    def handle_connect_action(
        self, transaction_id: int, data: bytes, addr: tuple[str, int]
    ) -> None:
        if len(data) < 16:
            logger.error(
                "[%s:%d] Connect response too short: received %d bytes (expected at least 16)",
                addr[0],
                addr[1],
                len(data),
            )
            return

        self.set_response_to_request(
            transaction_id, UDPTrackerAction.CONNECT, data, addr
        )

    def handle_announce_action(
        self, transaction_id: int, data: bytes, addr: tuple[str, int]
    ) -> None:
        if len(data) < 20:
            logger.error(
                "[%s:%d] Announce response too short: received %d bytes (expected at least 20)",
                addr[0],
                addr[1],
                len(data),
            )
            return

        self.set_response_to_request(
            transaction_id, UDPTrackerAction.ANNOUNCE, data, addr
        )

    def handle_scrape_action(
        self, transaction_id: int, data: bytes, addr: tuple[str, int]
    ) -> None:
        if len(data) < 8:
            logger.error(
                "[%s:%d] Scrape response too short: received %d bytes (expected at least 8)",
                addr[0],
                addr[1],
                len(data),
            )
            return

        self.set_response_to_request(
            transaction_id, UDPTrackerAction.SCRAPE, data, addr
        )

    def handle_error_action(
        self, transaction_id: int, data: bytes, addr: tuple[str, int]
    ) -> None:
        if len(data) < 8:
            logger.error(
                "[%s:%d] Error response too short: received %d bytes (expected at least 16)",
                addr[0],
                addr[1],
                len(data),
            )
            return

        self.set_response_to_request(transaction_id, UDPTrackerAction.ERROR, data, addr)

    def handle_unsupported_action(
        self, transaction_id: int, action: int, data: bytes, addr: tuple[str, int]
    ) -> None:
        self.set_response_to_request(transaction_id, action, data, addr)

    def handle_transaction_response(
        self, transaction_id: int, data: bytes, addr: tuple[str, int]
    ) -> None:
        action = struct.unpack_from("!I", data)[0]
        if action == UDPTrackerAction.CONNECT:
            self.handle_connect_action(transaction_id, data, addr)
        elif action == UDPTrackerAction.ANNOUNCE:
            self.handle_announce_action(transaction_id, data, addr)
        elif action == UDPTrackerAction.SCRAPE:
            self.handle_scrape_action(transaction_id, data, addr)
        elif action == UDPTrackerAction.ERROR:
            self.handle_error_action(transaction_id, data, addr)
        else:
            logger.error(
                "[%s:%d] Unsupported action received: %d", addr[0], addr[1], action
            )
            self.handle_unsupported_action(transaction_id, action, data, addr)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) < 8:
            logger.error(
                "[%s:%d] Received invalid datagram: too short to process",
                addr[0],
                addr[1],
            )
            return

        transaction_id: int = struct.unpack_from("!I", data, 4)[0]
        if transaction_id not in self._pending_requests:
            logger.error(
                "[%s:%d] Received response with unknown transaction ID: %d",
                addr[0],
                addr[1],
                transaction_id,
            )
            return

        self.handle_transaction_response(transaction_id, data, addr)

    async def receive_datagram(
        self, transaction_id: int, timeout: int | None = None
    ) -> tuple[UDPTrackerAction | int, bytes, tuple[str, int]]:
        future = self.get_pending_request(transaction_id)

        try:
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            raise UDPTrackerTimeout

    def send_datagram(self, transaction_id: int, datagram: bytes) -> None:
        if self._transport is None:
            raise RuntimeError("Transport is not available yet")

        self.create_request(transaction_id)
        self._transport.sendto(datagram)

    def close(self) -> None:
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()

        self._pending_requests.clear()

        if self._transport:
            self._transport.close()
            self._transport = None
