"""Shared helpers for protocol framing and socket I/O.

This module implements the low-level transport rules described in the project
summary:
- JSON control messages are length-prefixed.
- File contents are transferred as raw bytes.
- The protocol layer is shared so both client and server follow identical
  framing rules.
"""

import json
import socket
from typing import Any

from shared.config import (
    ENCODING,
    JSON_SEPARATORS,
    LENGTH_PREFIX_BYTEORDER,
    LENGTH_PREFIX_SIZE,
    SOCKET_CHUNK_SIZE,
)


def _validate_message_dict(message: dict[str, Any]) -> dict[str, Any]:
    """Validate a message object before JSON encoding.

    :param message: Candidate message object.
    :returns: The original message when it is a dictionary.
    :raises TypeError: If ``message`` is not a dictionary.
    """
    if not isinstance(message, dict):
        raise TypeError("message must be a dictionary.")
    return message


def _validate_bytes(data: bytes) -> bytes:
    """Validate that a socket payload is raw bytes.

    :param data: Payload that will be sent or decoded.
    :returns: The original payload when it is bytes.
    :raises TypeError: If ``data`` is not bytes.
    """
    if isinstance(data, bytes):
        return data

    raise TypeError("data must be bytes-like.")


def encode_message(message: dict[str, Any]) -> bytes:
    """Encode one protocol message to ``length-prefix + JSON payload`` bytes.

    :param message: Protocol message dictionary.
    :returns: Length-prefixed JSON bytes ready to send over the socket.
    :raises TypeError: If ``message`` is not a dictionary.
    """
    json_bytes = json.dumps(
        _validate_message_dict(message),
        ensure_ascii=False,
        separators=JSON_SEPARATORS,
    ).encode(ENCODING)
    length_prefix = len(json_bytes).to_bytes(
        LENGTH_PREFIX_SIZE,
        LENGTH_PREFIX_BYTEORDER,
    )
    return length_prefix + json_bytes


def decode_message(prefixed_bytes: bytes) -> dict[str, Any]:
    """Decode one complete framed JSON message.

    The caller must provide the full message, including the 4-byte length
    prefix.

    :param prefixed_bytes: Complete framed message as received from the wire.
    :returns: Parsed JSON object as a dictionary.
    :raises TypeError: If ``prefixed_bytes`` is not bytes.
    :raises ValueError: If the frame is too short, the prefix does not match
        the payload length, or the decoded JSON value is not an object.
    :raises json.JSONDecodeError: If the payload is not valid JSON text.
    """
    message_bytes = _validate_bytes(prefixed_bytes)
    if len(message_bytes) < LENGTH_PREFIX_SIZE:
        raise ValueError("Prefixed message is shorter than the length prefix.")

    length_prefix = message_bytes[:LENGTH_PREFIX_SIZE]
    payload_length = int.from_bytes(length_prefix, LENGTH_PREFIX_BYTEORDER)
    payload_bytes = message_bytes[LENGTH_PREFIX_SIZE:]

    if len(payload_bytes) != payload_length:
        raise ValueError(
            "Prefixed message payload length does not match its 4-byte prefix."
        )

    decoded_message = json.loads(payload_bytes.decode(ENCODING))
    if not isinstance(decoded_message, dict):
        raise ValueError("Decoded JSON message must be an object.")
    return decoded_message


def send_all(sock: socket.socket, data: bytes) -> None:
    """Send a complete bytes payload through a socket.

    :param sock: Connected socket used for the send.
    :param data: Raw bytes to transmit.
    :raises TypeError: If ``data`` is not bytes.
    :raises OSError: If the underlying socket send fails.
    """
    sock.sendall(_validate_bytes(data))


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive exactly ``size`` bytes from a socket.

    :param sock: Connected socket used for the receive.
    :param size: Number of bytes the caller expects.
    :returns: Exactly ``size`` bytes, or ``b""`` when ``size`` is zero.
    :raises TypeError: If ``size`` is not an integer.
    :raises ValueError: If ``size`` is negative.
    :raises ConnectionError: If the socket closes before all expected bytes are
        received.
    """
    if not isinstance(size, int):
        raise TypeError("size must be an integer.")
    if size < 0:
        raise ValueError("size cannot be negative.")
    if size == 0:
        return b""

    chunks: list[bytes] = []
    bytes_remaining = size

    # Raw file transfers may be large, so receive them in bounded chunks
    # rather than attempting a single read.
    while bytes_remaining > 0:
        chunk = sock.recv(min(SOCKET_CHUNK_SIZE, bytes_remaining))
        if not chunk:
            raise ConnectionError(
                f"Socket closed before receiving the expected {size} bytes."
            )
        chunks.append(chunk)
        bytes_remaining -= len(chunk)

    return b"".join(chunks)


def recv_message_bytes(sock: socket.socket) -> bytes:
    """Receive one complete length-prefixed JSON message.

    :param sock: Connected socket used for the receive.
    :returns: Full framed message, including the length prefix.
    :raises ConnectionError: If the socket closes during the prefix or payload
        receive.
    """
    length_prefix = recv_exact(sock, LENGTH_PREFIX_SIZE)
    payload_length = int.from_bytes(length_prefix, LENGTH_PREFIX_BYTEORDER)
    payload_bytes = recv_exact(sock, payload_length)
    return length_prefix + payload_bytes


def recv_message_bytes_or_none(sock: socket.socket) -> bytes | None:
    """Receive one complete JSON message or ``None`` on a clean EOF.

    ``None`` is returned only when the peer closes the socket before starting
    the next message length prefix. Partial prefixes or payloads still raise
    :class:`ConnectionError` because they represent a truncated transfer rather
    than a clean disconnect.

    :param sock: Connected socket used for the receive.
    :returns: Full framed message, including the length prefix, or ``None`` on
        a clean idle disconnect.
    :raises ConnectionError: If the socket closes after a message has started
        but before it finishes.
    """
    prefix_chunks: list[bytes] = []
    bytes_remaining = LENGTH_PREFIX_SIZE

    while bytes_remaining > 0:
        chunk = sock.recv(min(SOCKET_CHUNK_SIZE, bytes_remaining))
        if not chunk:
            if not prefix_chunks:
                return None
            raise ConnectionError("Socket closed while receiving the message length prefix.")
        prefix_chunks.append(chunk)
        bytes_remaining -= len(chunk)

    length_prefix = b"".join(prefix_chunks)
    payload_length = int.from_bytes(length_prefix, LENGTH_PREFIX_BYTEORDER)
    payload_bytes = recv_exact(sock, payload_length)
    return length_prefix + payload_bytes
