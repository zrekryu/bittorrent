import logging
import struct
from contextlib import suppress
from typing import Any, ClassVar, Final, cast

import bencode
from httpx import AsyncClient, ConnectTimeout, RequestError, Response

from bittorrent.enums import HTTPTrackerEvent
from bittorrent.exceptions import HTTPTrackerError, HTTPTrackerTimeout
from bittorrent.utils import (
    append_params_to_url,
    derive_scrape_url,
    generate_tracker_key,
    parse_compact_ipv4_peers,
    parse_compact_ipv6_peers,
    parse_ipv4_peers_list,
    parse_ipv6_peers_list,
)

from .responses import (
    HTTPTrackerAnnounceResponse,
    HTTPTrackerScrapedFile,
    HTTPTrackerScrapeResponse,
)

logger = logging.getLogger(__name__)


class HTTPTrackerClient:
    TIMEOUT: ClassVar[Final[int]] = 10
    NUM_WANT: ClassVar[Final[int]] = 50

    def __init__(self, announce_url: str, timeout: int = TIMEOUT) -> None:
        self._announce_url = announce_url

        self.scrape_url: str | None = None
        with suppress(ValueError):
            self.scrape_url = derive_scrape_url(self.announce_url)

        self.timeout = timeout

        self._client: AsyncClient = AsyncClient(timeout=self.timeout)

        self.tracker_id: str | None = None

    @property
    def announce_url(self) -> str:
        return self._announce_url

    def supports_scrape(self) -> bool:
        return self.scrape_url is not None

    @staticmethod
    def prepare_announce_url(
        announce_url: str,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        uploaded: int,
        downloaded: int,
        left: int,
        compact: bool = True,
        event: HTTPTrackerEvent | str | None = None,
        num_want: int = NUM_WANT,
        ipv6: bool = False,
        ip: str | None = None,
        tracker_id: str | None = None,
    ) -> str:
        params: dict[str, bytes | int | str] = {
            "info_hash": info_hash,
            "peer_id": peer_id,
            "port": port,
            "uploaded": uploaded,
            "downloaded": downloaded,
            "left": left,
            "key": generate_tracker_key(),
        }

        if compact:
            params["compact"] = compact
        if event is not None:
            params["event"] = event

        if num_want is not None:
            params["numwant"] = num_want

        if ipv6 is not None:
            params["ipv6"] = ipv6
        if ip:
            params["ip"] = ip

        if tracker_id is not None:
            params["trackerid"] = tracker_id

        return append_params_to_url(announce_url, params)

    async def send_announce(self, announce_url: str, timeout: int | None = None) -> dict[bytes, Any]:
        try:
            response: Response = await self._client.get(announce_url, timeout=timeout or self.timeout)
        except ConnectTimeout:
            raise HTTPTrackerTimeout("Announce request timed out")
        except RequestError as exc:
            raise HTTPTrackerError(f"Announce request failed: {exc}")

        decoded_response: dict[bytes, Any]
        failure_reason: str | None

        if response.status_code != 200:
            try:
                decoded_response = cast(
                    dict[bytes, Any], bencode.decode(response.content)
                )
            except bencode.BencodeDecodeError:
                error_msg = f"Announce request failed: {response.reason_phrase} (status code: {response.status_code})"
                logger.debug(error_msg)
                raise HTTPTrackerError(error_msg)

            if failure_reason := decoded_response.get(b"failure reason"):
                failure_reason = failure_reason.decode("utf-8")
            else:
                failure_reason = response.reason_phrase

            error_msg = f"Announce request failed: {failure_reason} (status code: {response.status_code})"
            logger.debug(error_msg)
            raise HTTPTrackerError(error_msg)

        try:
            decoded_response = cast(dict[bytes, Any], bencode.decode(response.content))
        except bencode.BencodeDecodeError as exc:
            error_msg = f"Failed to decode announce response: {exc}"
            logger.debug(error_msg)
            raise HTTPTrackerError(error_msg)

        if failure_reason := decoded_response.get(b"failure reason"):
            error_msg = f"Announce request failed: {failure_reason.decode('utf-8')}"
            logger.debug(error_msg)
            raise HTTPTrackerError(error_msg)

        return decoded_response

    @staticmethod
    def parse_announce_response(
        response: dict[bytes, Any],
    ) -> HTTPTrackerAnnounceResponse:
        try:
            interval: int = response[b"interval"]
        except KeyError as key:
            raise HTTPTrackerError(f"Missing key in announce response: {key}")

        complete: int | None = response.get(b"complete")
        incomplete: int | None = response.get(b"incomplete")

        peers: list[tuple[str, int]] = []

        if raw_peers := response.get(b"peers"):
            if isinstance(raw_peers, list):
                try:
                    peers = parse_ipv4_peers_list(raw_peers)
                except (TypeError, ValueError) as exc:
                    raise HTTPTrackerError(
                        f"Failed to parse IPv4 peers list from announce response: {exc}"
                    )
            elif isinstance(raw_peers, bytes):
                try:
                    peers = parse_compact_ipv4_peers(raw_peers)
                except (ValueError, struct.error) as exc:
                    raise HTTPTrackerError(
                        f"Failed to parse compact IPv4 peers from announce response: {exc}"
                    )

        peers6: list[tuple[str, int]] = []
        if raw_peers6 := response.get(b"peers6"):
            if isinstance(raw_peers6, list):
                try:
                    peers6 = parse_ipv6_peers_list(raw_peers6)
                except (TypeError, ValueError) as exc:
                    raise HTTPTrackerError(
                        f"Failed to parse IPv6 peers list from announce response: {exc}"
                    )
            elif isinstance(raw_peers6, bytes):
                try:
                    peers6 = parse_compact_ipv6_peers(raw_peers6)
                except (ValueError, struct.error) as exc:
                    raise HTTPTrackerError(
                        f"Failed to parse compact IPv6 peers from announce response: {exc}"
                    )

        min_interval: int | None = response.get(b"min interval")

        tracker_id: str | None = (
            tid.decode("utf-8") if (tid := response.get(b"tracker id")) else None
        )

        warning_message: str | None = (
            warning_msg.decode("utf-8")
            if (warning_msg := response.get(b"warning message"))
            else None
        )

        return HTTPTrackerAnnounceResponse(
            interval=interval,
            complete=complete,
            incomplete=incomplete,
            peers=peers,
            peers6=peers6,
            min_interval=min_interval,
            tracker_id=tracker_id,
            warning_message=warning_message,
        )

    async def announce(
        self,
        info_hash: bytes,
        peer_id: bytes,
        port: int,
        uploaded: int,
        downloaded: int,
        left: int,
        compact: bool = True,
        event: HTTPTrackerEvent | str | None = None,
        num_want: int = NUM_WANT,
        ipv6: bool = False,
        ip: str | None = None,
        tracker_id: str | None = None,
        timeout: int | None = None
    ) -> HTTPTrackerAnnounceResponse:
        announce_url: str = self.prepare_announce_url(
            announce_url=self.announce_url,
            info_hash=info_hash,
            peer_id=peer_id,
            port=port,
            uploaded=uploaded,
            downloaded=downloaded,
            left=left,
            compact=compact,
            event=event,
            num_want=num_want,
            ipv6=ipv6,
            ip=ip,
            tracker_id=tracker_id or self.tracker_id,
        )

        decoded_response: dict[bytes, Any] = await self.send_announce(announce_url, timeout)
        response: HTTPTrackerAnnounceResponse = self.parse_announce_response(
            decoded_response
        )

        if response.tracker_id:
            self.tracker_id = response.tracker_id

        return response

    @staticmethod
    def prepare_scrape_url(
        scrape_url: str, info_hashes: list[bytes] | bytes | None = None
    ) -> str:
        params: dict[str, list[bytes] | bytes] = {}
        if info_hashes is not None:
            params["info_hash"] = info_hashes

        return append_params_to_url(scrape_url, params)

    async def send_scrape(
        self, scrape_url: str, timeout: int | None = None
    ) -> dict[bytes, bencode.BencodeDataTypes]:
        try:
            response: Response = await self._client.get(scrape_url, timeout=timeout or self.timeout)
        except ConnectTimeout:
            raise HTTPTrackerTimeout("Scrape request timed out")
        except RequestError as exc:
            raise HTTPTrackerError(f"Scrape request failed: {exc}")

        decoded_response: dict[bytes, Any]
        failure_reason: str | None

        if response.status_code != 200:
            try:
                decoded_response = cast(
                    dict[bytes, Any], bencode.decode(response.content)
                )
            except bencode.BencodeDecodeError:
                error_msg = f"Scrape request failed (status code: {response.status_code}): {response.reason_phrase}"
                logger.debug(error_msg)
                raise HTTPTrackerError(error_msg)

            if failure_reason := decoded_response.get(b"failure reason"):
                failure_reason = failure_reason.decode("utf-8")
            else:
                failure_reason = response.reason_phrase

            error_msg = f"Scrape request failed (status code: {response.status_code}): {failure_reason}"
            logger.debug(error_msg)
            raise HTTPTrackerError(error_msg)

        try:
            decoded_response = cast(dict[bytes, Any], bencode.decode(response.content))
        except bencode.BencodeDecodeError as exc:
            error_msg = f"Failed to decode scrape response: {exc}"
            logger.debug(error_msg)
            raise HTTPTrackerError(error_msg)

        if failure_reason := decoded_response.get(b"failure reason"):
            error_msg = f"Scrape request failed: {failure_reason.decode('utf-8')}"
            logger.debug(error_msg)
            raise HTTPTrackerError(error_msg)

        return decoded_response

    @staticmethod
    def parse_scrape_response(response: dict[bytes, Any]) -> HTTPTrackerScrapeResponse:
        try:
            raw_files: dict[bytes, dict[bytes, Any]] = response[b"files"]
        except KeyError as key:
            raise HTTPTrackerError(f"Missing key in scrape response: {key}")

        files: dict[bytes, HTTPTrackerScrapedFile] = {}
        for info_hash, raw_file in raw_files.items():
            try:
                complete: int = raw_file[b"complete"]
            except KeyError as key:
                raise HTTPTrackerError(
                    f"Missing key in scrape file entry: {key!r} (info hash: {info_hash!r})"
                )

            try:
                incomplete: int = raw_file[b"incomplete"]
            except KeyError as key:
                raise HTTPTrackerError(
                    f"Missing key in scrape file entry: {key!r} (info hash: {info_hash!r})"
                )

            try:
                downloaded: int = raw_file[b"downloaded"]
            except KeyError as key:
                raise HTTPTrackerError(
                    f"Missing key in scrape file entry: {key!r} (info hash: {info_hash!r})"
                )

            files[info_hash] = HTTPTrackerScrapedFile(
                complete=complete,
                incomplete=incomplete,
                downloaded=downloaded,
                name=name.decode("utf-8") if (name := raw_file.get(b"name")) else None,
            )

        return HTTPTrackerScrapeResponse(files)

    async def scrape(
        self,
        info_hashes: list[bytes] | bytes | None = None,
        timeout: int | None = None
    ) -> HTTPTrackerScrapeResponse:
        if not self.supports_scrape():
            raise HTTPTrackerError("Tracker does not support scrape requests")

        assert self.scrape_url is not None

        scrape_url: str = self.prepare_scrape_url(self.scrape_url, info_hashes)

        decoded_response: dict[bytes, Any] = await self.send_scrape(scrape_url, timeout)

        return self.parse_scrape_response(decoded_response)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

        self.tracker_id = None

    def __repr__(self) -> str:
        return (
            "HTTPTracker("
            f"announce_url={self.announce_url!r}, "
            f"scrape_url={self.scrape_url!r}, "
            f"tracker_id={self.tracker_id!r}"
            ")"
        )
