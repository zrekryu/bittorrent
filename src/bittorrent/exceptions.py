class BitTorrentError(Exception):
    pass


class TorrentMetadataError(BitTorrentError):
    pass


class TorrentMetadataMissingKeyError(TorrentMetadataError):
    pass


class TorrentMetadataInvalidTypeError(TorrentMetadataError):
    pass


class TorrentMetadataInvalidValueError(TorrentMetadataError):
    pass


class TrackerError(BitTorrentError):
    pass


class HTTPTrackerError(TrackerError):
    pass


class HTTPTrackerTimeout(HTTPTrackerError):
    pass


class UDPTrackerError(TrackerError):
    pass


class UDPTrackerTimeout(UDPTrackerError):
    pass


class UDPTrackerConnectionIDExpired(UDPTrackerError):
    pass


class PeerConnectionError(BitTorrentError):
    pass


class PeerConnectionTimeout(BitTorrentError):
    pass


class PeerHandshakeError(BitTorrentError):
    pass