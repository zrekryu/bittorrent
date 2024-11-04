from urllib.parse import urlparse, ParseResult
import asyncio
import socket
import struct
import secrets
import hashlib
import os
import ipaddress
from typing import Any

import libbencode

from .protocol.peer_address import PeerAddress

def generate_transaction_id() -> int:
    return int.from_bytes(os.urandom(4), byteorder="big")

def generate_tracker_key(protocol: str) -> str | int:
    match protocol:
        case "http":
            return secrets.token_urlsafe(16)
        case "udp":
            return int.from_bytes(os.urandom(4), byteorder="big")
        case _:
            raise ValueError(f"Unsupported protocol: {protocol}")

def generate_info_hash(info: dict[bytes, Any]) -> bytes:
    return hashlib.sha1(libbencode.encode(info)).digest()

def generate_peer_id(prefix: bytes | None = None, sep: bytes = b"-") -> bytes:
    if prefix is None:
        prefix = os.urandom(10)
    
    length: int = 20 - len(prefix) - len(sep)
    if length < 0:
        raise ValueError("Prefix and separator combined length exceeds the maximum allowed length (20 bytes)")
    
    return prefix + sep + os.urandom(length)

def decode_announce_list(announce_list: list[list[bytes]]) -> list[list[str]]:
    return [[uri.decode("utf-8")] for urilist in announce_list for uri in urilist]

def parse_tracker_uri(uri: str) -> tuple[str, str | tuple[str, int]]:
    parsed_uri: ParseResult = urlparse(uri)
    scheme: str = parsed_uri.scheme
    
    if scheme.startswith("http"):
        return (scheme, parsed_uri.geturl())
    elif scheme.startswith("udp"):
        if parsed_uri.hostname is None:
            raise ValueError("UDP URI does not have hostname")
        elif parsed_uri.port is None:
            raise ValueError("UDP URI does not have a port")
        
        return (scheme, (parsed_uri.hostname, parsed_uri.port))
    else:
        raise ValueError(f"Unsupported tracker URI scheme: {scheme}")

def decode_compact_peers(data: bytes) -> list[PeerAddress]:
    return [
        PeerAddress(
            host=socket.inet_ntoa(data[i:i+4]),
            port=struct.unpack(">H", data[i+4:i+6])[0]
            )
        for i in range(0, len(data), 6)
        ]

async def get_free_bittorrent_port() -> int:
    for port in range(6881, 6889+1):
        try:
            _, writer = await asyncio.open_connection(socket.gethostname(), port)
            
            writer.close()
            await writer.wait_closed()
        except OSError:
            return port
    else:
        raise RuntimeError("No free port found in the range (6881-6889)")

def convert_ip_to_integer(ip_address: str) -> int:
    ip_version: int = ipaddress.ip_address(ip_address).version
    
    match ip_version:
        case 4:
            return struct.unpack(">I", socket.inet_aton(ip_address))[0]
        case 6:
            return int.from_bytes(socket.inet_pton(socket.AF_INET6, ip_address), byteorder="big")
        case _:
            raise ValueError(f"Unsupported IP version: {ip_version}")

def create_peer_addresses(peer_addresses: list[tuple[str, int]]) -> list[PeerAddress]:
    return [PeerAddress(host, port) for host, port in peer_addresses]