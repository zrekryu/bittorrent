import os
from hashlib import sha1, sha256
from typing import Any

import bencode

from ..metadata.models import TorrentMetadataInfo


def calculate_torrent_total_length(info: TorrentMetadataInfo) -> int:
    if info.length is not None:
        return info.length
    elif info.files is not None:
        return sum(file.length for file in info.files)
    elif info.file_tree is not None:
        raise NotImplementedError
    else:
        raise ValueError("No source found for calculating torrent's total length")


def generate_info_hash_sha1(info: dict[str | bytes, Any]) -> bytes:
    return sha1(bencode.encode(info, sort_keys=True)).digest()


def generate_info_hash_sha256(info: dict[str | bytes, Any]) -> bytes:
    return sha256(bencode.encode(info, sort_keys=True)).digest()


def generate_peer_id() -> bytes:
    return os.urandom(20)
