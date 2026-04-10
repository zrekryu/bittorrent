from datetime import datetime, timezone
from typing import Any, cast

from bencode import BencodeDataTypes
from bittorrent.exceptions import (
    TorrentMetadataInvalidTypeError,
    TorrentMetadataInvalidValueError,
    TorrentMetadataMissingKeyError,
)

from ..keys import SUPPORTED_ROOT_KEYS
from ..models import TorrentMetadata, TorrentMetadataDHTNode, TorrentMetadataInfo
from .info_parser import TorrentMetadataInfoParser


class TorrentMetadataParser:
    def __init__(self, metadata: dict[bytes, BencodeDataTypes]) -> None:
        self.metadata = metadata

    def parser_info(self) -> TorrentMetadataInfo:
        key = b"info"
        raw_info: BencodeDataTypes | None = self.metadata.get(key)

        if raw_info is None:
            raise TorrentMetadataMissingKeyError(f"Missing key: {key!r}")

        if not isinstance(raw_info, dict):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be a dict, got {type(raw_info).__name__} instead"
            )

        info_parser = TorrentMetadataInfoParser(raw_info)
        return info_parser.parse()

    def parse_piece_layers(self) -> dict[bytes, bytes] | None:
        key = b"piece layers"
        piece_layers: BencodeDataTypes | None = self.metadata.get(key)

        if piece_layers is None:
            return None

        if not isinstance(piece_layers, dict):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be a dict, got {type(piece_layers).__name__} instead"
            )

        for pieces_root, piece_layer in piece_layers.items():
            if not isinstance(pieces_root, bytes):
                raise TorrentMetadataInvalidTypeError(
                    f"Pieces root must be bytes, got {type(pieces_root).__name__} instead (key: {key!r})"
                )

            if not isinstance(piece_layer, bytes):
                raise TorrentMetadataInvalidTypeError(
                    f"Piece layer must be bytes, got {type(piece_layer).__name__} instead"
                    f"(key: {key!r}, pieces root: {pieces_root!r})"
                )

        return cast(dict[bytes, bytes], piece_layers)

    def parse_announce(self) -> str | None:
        key = b"announce"
        announce: BencodeDataTypes | None = self.metadata.get(key)

        if announce is None:
            return None

        if not isinstance(announce, bytes):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be bytes, got {type(announce).__name__} instead"
            )

        return announce.decode("utf-8")

    def parse_announce_list(self) -> list[list[str]] | None:
        key = b"announce-list"
        raw_announce_list: BencodeDataTypes | None = self.metadata.get(key)

        if raw_announce_list is None:
            return None

        if not isinstance(raw_announce_list, list):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be a list, got {type(raw_announce_list).__name__} instead"
            )

        tiers: list[list[str]] = []
        for tier_index, tier in enumerate(raw_announce_list):
            if not isinstance(tier, list):
                raise TorrentMetadataInvalidTypeError(
                    f"Tier must be a list, got {type(tier).__name__} instead"
                    f"(key: {key!r}, tier index: {tier_index})"
                )

            urls: list[str] = []
            for url_index, url in enumerate(tier):
                if not isinstance(url, bytes):
                    raise TorrentMetadataInvalidTypeError(
                        f"Announce URL must be bytes, got {type(url).__name__} instead"
                        f"(key: {key!r}, tier index: {tier_index}, URL index: {url_index})"
                    )

                urls.append(url.decode("utf-8"))

            tiers.append(urls)

        return tiers

    def parse_url_list(self) -> list[str] | None:
        key = b"url-list"
        raw_url_list: BencodeDataTypes | None = self.metadata.get(key)

        if raw_url_list is None:
            return None

        if not isinstance(raw_url_list, list):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be a list, got {type(raw_url_list).__name__} instead"
            )

        url_list: list[str] = []
        for i, url in enumerate(raw_url_list):
            if not isinstance(url, bytes):
                raise TorrentMetadataInvalidTypeError(
                    f"URL be must bytes, got {type(url).__name__} instead"
                    f"(key: {key!r}, url index: {i})"
                )

            url_list.append(url.decode("utf-8"))

        return url_list

    def parse_nodes(self) -> list[TorrentMetadataDHTNode] | None:
        key = b"nodes"

        raw_nodes: BencodeDataTypes | None = self.metadata.get(key)
        if raw_nodes is None:
            return None

        if not isinstance(raw_nodes, list):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be a list, got {type(raw_nodes).__name__} instead"
            )

        nodes: list[TorrentMetadataDHTNode] = []
        for i, node in enumerate(raw_nodes):
            if not isinstance(node, list):
                raise TorrentMetadataInvalidTypeError(
                    f"Node must be a tuple, got {type(node).__name__} instead"
                    f"(key: {key!r}, node index: {i})"
                )

            if len(node) < 2:
                raise TorrentMetadataInvalidValueError(
                    f"Node must contain at least two elements (host and port)"
                    f"(key: {key!r}, node index: {i})"
                )

            hostname: BencodeDataTypes = node[0]
            port: BencodeDataTypes = node[1]

            if not isinstance(hostname, bytes):
                raise TorrentMetadataInvalidTypeError(
                    f"Hostname must be bytes, got {type(hostname).__name__} instead"
                    f"(key: {key!r}, node index: {i})"
                )

            if not isinstance(port, int):
                raise TorrentMetadataInvalidTypeError(
                    f"Port must be an int, got {type(port).__name__} instead"
                    f"(key: {key!r}, node index: {i})"
                )

            nodes.append(
                TorrentMetadataDHTNode(hostname=hostname.decode("utf-8"), port=port)
            )

        return nodes

    def parse_creation_date(self) -> datetime | None:
        key = b"creation date"
        creation_date: BencodeDataTypes | None = self.metadata.get(key)

        if creation_date is None:
            return None

        if not isinstance(creation_date, int):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be an int, got {type(creation_date).__name__} instead"
            )

        if creation_date < 0:
            raise TorrentMetadataInvalidValueError(
                f"Key {key!r} must be a non-negative, got {creation_date} instead"
            )

        return datetime.fromtimestamp(creation_date, tz=timezone.utc)

    def parse_created_by(self) -> str | None:
        key_utf8 = b"created by.utf-8"
        key = key_utf8 if key_utf8 in self.metadata else b"created by"
        created_by: BencodeDataTypes | None = self.metadata.get(key)

        if created_by is None:
            return None

        if not isinstance(created_by, bytes):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be bytes, got {type(created_by).__name__} instead"
            )

        return created_by.decode("utf-8")

    def parse_comment(self) -> str | None:
        key_utf8 = b"comment.utf-8"
        key = key_utf8 if key_utf8 in self.metadata else b"comment"
        comment: BencodeDataTypes | None = self.metadata.get(key)

        if comment is None:
            return None

        if not isinstance(comment, bytes):
            raise TorrentMetadataInvalidTypeError(
                f"Key {key!r} must be bytes, got {type(comment).__name__} instead"
            )

        return comment.decode("utf-8")

    def extract_extra_keys(self) -> dict[bytes, Any]:
        return {k: v for k, v in self.metadata.items() if k not in SUPPORTED_ROOT_KEYS}

    def parse(self, extract_extra_keys: bool = True) -> TorrentMetadata:
        return TorrentMetadata(
            info=self.parser_info(),
            piece_layers=self.parse_piece_layers(),
            announce=self.parse_announce(),
            announce_list=self.parse_announce_list(),
            url_list=self.parse_url_list(),
            nodes=self.parse_nodes(),
            creation_date=self.parse_creation_date(),
            created_by=self.parse_created_by(),
            comment=self.parse_comment(),
            **({"extra_keys": self.extract_extra_keys()} if extract_extra_keys else {}),
        )
