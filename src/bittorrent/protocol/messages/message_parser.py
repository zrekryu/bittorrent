from ...exceptions import UnknownMessageError

from .message import Message
from .keep_alive import KeepAlive
from .choke import Choke
from .unchoke import Unchoke
from .interested import Interested
from .not_interested import NotInterested
from .have import Have
from .bitfield import BitField
from .request import Request
from .piece import Piece
from .cancel import Cancel
from .port import Port

message_id_to_class: dict[int, type[Message]] = {
    Choke.MESSAGE_ID: Choke,
    Unchoke.MESSAGE_ID: Unchoke,
    Interested.MESSAGE_ID: Interested,
    NotInterested.MESSAGE_ID: NotInterested,
    Have.MESSAGE_ID: Have,
    BitField.MESSAGE_ID: BitField,
    Request.MESSAGE_ID: Request,
    Piece.MESSAGE_ID: Piece,
    Cancel.MESSAGE_ID: Cancel,
    Port.MESSAGE_ID: Port
}

def message_supports_from_bytes(message_id: int) -> bool:
    return message_id not in {
        Choke.MESSAGE_ID,
        Unchoke.MESSAGE_ID,
        Interested.MESSAGE_ID,
        NotInterested.MESSAGE_ID
    }

def parse_message(message_length: int, message_id: int | None = None, payload: bytes | None = None) -> Message:
    if message_length == 0:
        return KeepAlive()
    elif message_id is None:
        raise ValueError("Message length is not zero and message ID is not provided")
    
    message_class: type[Message] | None = message_id_to_class.get(message_id, None)
    
    if message_class is None:
        raise UnknownMessageError(message_id, payload)
    
    return message_class.from_bytes(payload) if payload and message_supports_from_bytes(message_id) else message_class()