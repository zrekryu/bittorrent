import secrets
import struct
from collections.abc import Buffer, Mapping, Sequence
from ipaddress import IPv4Address, IPv6Address
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

__all__ = [
    "append_params_to_url",
    "derive_scrape_url",
    "extract_udp_tracker_addr",
    "generate_tracker_key",
    "generate_transaction_id",
    "ipv4_str_to_int",
    "parse_compact_ipv4_peers",
    "parse_compact_ipv6_peers",
    "parse_ipv4_peers_list",
    "parse_ipv6_peers_list"
]


type QueryParamsType = Mapping[
    str, int | bool | float | str | bytes | Sequence[int | bool | float | str | bytes]
]


# HTTP Tracker utils:


def append_params_to_url(url: str, params: QueryParamsType) -> str:
    parsed = urlparse(url)
    existing_params = parse_qsl(parsed.query)

    new_params = [(k, v) for k, v in params.items()]
    all_params = existing_params + new_params

    query = urlencode(all_params, doseq=True)
    return urlunparse(parsed._replace(query=query))


def derive_scrape_url(announce_url: str) -> str:
    parsed_url = urlparse(announce_url)

    path = PurePosixPath(parsed_url.path)
    if path.name != "announce":
        raise ValueError("Announce URL does not end with 'announce' path")

    scrape_path = path.with_name("scrape")
    return urlunparse(parsed_url._replace(path=str(scrape_path)))


def generate_tracker_key() -> int:
    return secrets.randbits(32)


def parse_ipv4_peers_list(
    peers: Sequence[Mapping[Buffer, Buffer | int]],
) -> list[tuple[str, int]]:
    return [(str(IPv4Address(peer[b"ip"])), int(peer[b"port"])) for peer in peers]


def parse_ipv6_peers_list(
    peers: Sequence[Mapping[Buffer, Buffer | int]],
) -> list[tuple[str, int]]:
    return [(str(IPv6Address(peer[b"ip"])), int(peer[b"port"])) for peer in peers]


def parse_compact_ipv4_peers(peers: Buffer) -> list[tuple[str, int]]:
    view = memoryview(peers)
    length = len(view)

    if length % 6 != 0:
        raise ValueError("Compact IPv4 peers must be multiple of 6")

    return [
        (
            str(IPv4Address(view[i : i + 4])),
            struct.unpack_from(">H", view, i + 4)[0]
        )
        for i in range(0, length, 6)
    ]


def parse_compact_ipv6_peers(peers: Buffer) -> list[tuple[str, int]]:
    view = memoryview(peers)
    length = len(view)

    if length % 18 != 0:
        raise ValueError("Compact IPv6 peers must be multiple of 18")

    return [
        (
            str(IPv6Address(view[i : i + 16])),
            struct.unpack_from(">H", view, i + 16)[0]
        )
        for i in range(0, length, 18)
    ]


# UDP Tracker utils:


def extract_udp_tracker_addr(announce_url: str) -> tuple[str, int]:
    parsed_url = urlparse(announce_url)
    if parsed_url.scheme != "udp":
        raise ValueError(
            f"Announce URL is not a UDP tracker, found: {parsed_url.scheme}"
        )

    if parsed_url.hostname is None:
        raise ValueError("Hostname must not be None")

    if parsed_url.port is None:
        raise ValueError("Port must not be None")

    return (parsed_url.hostname, parsed_url.port)


def ipv4_str_to_int(ipv4_str: str) -> int:
    return int(IPv4Address(ipv4_str))


def generate_transaction_id() -> int:
    return secrets.randbits(32)