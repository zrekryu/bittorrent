from .messages.abstract import AbstractPeerMessage
from .messages.bitfield import Bitfield
from .messages.cancel import Cancel
from .messages.choke import CHOKE
from .messages.have import Have
from .messages.interested import INTERESTED
from .messages.keep_alive import KEEP_ALIVE
from .messages.not_interested import NOT_INTERESTED
from .messages.piece import Piece
from .messages.port import Port
from .messages.request import Request
from .messages.unchoke import UNCHOKE

SINGLETON_MESSAGES: dict[int, AbstractPeerMessage] = {
    0: CHOKE,
    1: UNCHOKE,
    2: INTERESTED,
    3: NOT_INTERESTED
}


PAYLOAD_MESSAGES: dict[int, type[AbstractPeerMessage]] = {
    4: Have,
    5: Bitfield,
    6: Request,
    7: Piece,
    8: Cancel,
    9: Port
}


def parse_message(
    message_length: int = 0,
    message_id: int | None = None,
    payload: bytes | None = None
) -> AbstractPeerMessage:
    if message_length == 0:
        return KEEP_ALIVE

    if message_id is None:
        raise TypeError("message ID must not be None, when message length != 0")

    message: type[AbstractPeerMessage] | AbstractPeerMessage
    try:
        if payload is None:
            message = SINGLETON_MESSAGES[message_id]
        else:
            message = PAYLOAD_MESSAGES[message_id]
    except KeyError:
        raise ValueError(f"Unknown peer message ID: {message_id}")

    if payload is not None:
        return message.from_payload(payload)

    assert isinstance(message, AbstractPeerMessage)

    return message