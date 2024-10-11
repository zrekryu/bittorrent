class TrackerError(Exception):
    pass

class TrackerTierExhaustedError(Exception):
    pass

class TrackerAllTiersExhaustedError(Exception):
    pass

class PeerError(Exception):
    pass

class UnknownMessageError(Exception):
    def __init__(self, message_id: int, payload: bytes | None = None):
        self.message_id = message_id
        self.payload = payload
        
        super().__init__(f"Unknown message ID {self.message_id} with payload: {self.payload!r}")