from __future__ import annotations

import asyncio

from .peers import PeerConnection
from .peers.messages import AbstractPeerMessage
from .trackers import (
    HTTPTrackerAnnounceResponse,
    HTTPTrackerClient,
    UDPTrackerAnnounceResponse,
    UDPTrackerClient,
)

type TrackerClient = HTTPTrackerClient | UDPTrackerClient
type TrackerResponse = HTTPTrackerAnnounceResponse | UDPTrackerAnnounceResponse


type PeerMessageTuple = tuple[PeerConnection, AbstractPeerMessage]
type PeerMessageQueue = asyncio.Queue[PeerMessageTuple]