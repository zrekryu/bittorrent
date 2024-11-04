from ...exceptions import UnknownMessageError

from .message import Message
from .keep_alive_message import KeepAliveMessage
from .choke_message import ChokeMessage
from .unchoke_message import UnchokeMessage
from .interested_message import InterestedMessage
from .not_interested_message import NotInterestedMessage
from .have_message import HaveMessage
from .bitfield_message import BitFieldMessage
from .request_message import RequestMessage
from .piece_message import PieceMessage
from .cancel_message import CancelMessage
from .port_message import PortMessage

message_id_to_class: dict[int, type[Message]] = {
    ChokeMessage.MESSAGE_ID: ChokeMessage,
    UnchokeMessage.MESSAGE_ID: UnchokeMessage,
    InterestedMessage.MESSAGE_ID: InterestedMessage,
    NotInterestedMessage.MESSAGE_ID: NotInterestedMessage,
    HaveMessage.MESSAGE_ID: HaveMessage,
    BitFieldMessage.MESSAGE_ID: BitFieldMessage,
    RequestMessage.MESSAGE_ID: RequestMessage,
    PieceMessage.MESSAGE_ID: PieceMessage,
    CancelMessage.MESSAGE_ID: CancelMessage,
    PortMessage.MESSAGE_ID: PortMessage
}

def parse_message(message_length: int, message_id: int | None = None, payload: bytes | None = None) -> Message:
    if message_length == 0:
        return KeepAliveMessage()
    elif message_id is None:
        raise ValueError("Message length is not zero and message ID is not provided")
    
    message_class: type[Message] | None = message_id_to_class.get(message_id, None)
    
    if message_class is None:
        raise UnknownMessageError(message_id, payload)
    
    return message_class.from_bytes(payload) if payload and message_class.SUPPORTS_PAYLOAD else message_class()