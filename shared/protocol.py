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
    """Ensure a message is a dictionary to make sure it can be transformed into a JSON-object before encoding."""
    if not isinstance(message, dict):
        raise TypeError("message must be a dictionary.")
    return message


def _validate_bytes(data: bytes) -> bytes:
    """Ensure a socket payload is raw bytes."""
    if isinstance(data, bytes):
        return data

    raise TypeError("data must be bytes-like.")


def encode_message(message: dict[str, Any]) -> bytes:
    """Encode a message into ``length-prefix + JSON payload`` both as bytes."""
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
    """Decode a full prefixed JSON byte sequence back into a dictionary.

    The caller must provide one complete framed message, length prefix included
    
    ValueErrors needs to catched to prevent them crashing server
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
    """Send all bytes through a socket."""
    sock.sendall(_validate_bytes(data))


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive exactly ``size`` bytes or raise if the socket closes early."""
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
    """Receive one complete length-prefixed JSON message from a socket."""
    length_prefix = recv_exact(sock, LENGTH_PREFIX_SIZE)
    payload_length = int.from_bytes(length_prefix, LENGTH_PREFIX_BYTEORDER)
    payload_bytes = recv_exact(sock, payload_length)
    return length_prefix + payload_bytes


def recv_message_bytes_or_none(sock: socket.socket) -> bytes | None:
    """Receive one complete JSON message or ``None`` on a clean EOF.

    ``None`` is returned only when the peer closes the socket before sending the
    next message length prefix at all. Partial prefixes or payloads still raise
    ``ConnectionError`` because they indicate a broken transfer.
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
