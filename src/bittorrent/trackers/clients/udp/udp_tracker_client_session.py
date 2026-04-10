from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Final

from bittorrent.exceptions import UDPTrackerConnectionIDExpired


class UDPTrackerClientSession:
    CONNECTION_ID_TTL: Final[int] = 60

    def __init__(self, connection_id_ttl: int = CONNECTION_ID_TTL) -> None:
        self.connection_id_ttl = connection_id_ttl

        self._connection_id: int | None = None
        self._connection_id_expiration_time: float | None = None

        self._timeout: asyncio.Timeout | None = None

    def get_connection_id(self) -> int | None:
        return self._connection_id

    def set_connection_id(self, connection_id: int) -> None:
        self._connection_id = connection_id
        self._connection_id_expiration_time = (
            asyncio.get_running_loop().time() + self.connection_id_ttl
        )

    def has_connection_id(self) -> bool:
        return self._connection_id is not None

    def is_connection_expired(self) -> bool:
        return (
            self._connection_id is None
            or self._connection_id_expiration_time is None
            or self._connection_id_expiration_time <= asyncio.get_running_loop().time()
        )

    def remove_connection_id(self) -> None:
        self._connection_id = None
        self._connection_id_expiration_time = None
        self._timeout = None

    async def __aenter__(self) -> UDPTrackerClientSession:
        if self.is_connection_expired():
            self.remove_connection_id()
            raise UDPTrackerConnectionIDExpired

        self._timeout = asyncio.timeout_at(self._connection_id_expiration_time)
        await self._timeout.__aenter__()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._timeout is None:
            raise RuntimeError(
                f"{type(self).__name__}.__aenter__() must be awaited before using __aexit__()"
            )

        try:
            await self._timeout.__aexit__(exc_type, exc_value, traceback)
        except TimeoutError:
            raise UDPTrackerConnectionIDExpired

    def close(self) -> None:
        self.remove_connection_id()
        self._timeout = None
