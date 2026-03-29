"""shared helpers for protocol framing and socket I/O."""

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
    if not isinstance(message, dict):
        raise TypeError("message must be a dictionary.")
    return message


def _validate_bytes(data: bytes) -> bytes:
    if isinstance(data, bytes):
        return data

    raise TypeError("data must be bytes-like.")


def encode_message(message: dict[str, Any]) -> bytes:
    """Encode a protocol message into a prefixed JSON byte sequence."""
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
    """Decode a full prefixed JSON byte sequence back into a dictionary."""
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
    """Send a complete byte sequence through a socket."""
    sock.sendall(_validate_bytes(data))


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive an exact number of bytes from a socket."""
    if not isinstance(size, int):
        raise TypeError("size must be an integer.")
    if size < 0:
        raise ValueError("size cannot be negative.")
    if size == 0:
        return b""

    chunks: list[bytes] = []
    bytes_remaining = size

    # Raw file transfers may be large, so receive them in bounded chunks.
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
    """Receive one full prefixed JSON message from a socket."""
    length_prefix = recv_exact(sock, LENGTH_PREFIX_SIZE)
    payload_length = int.from_bytes(length_prefix, LENGTH_PREFIX_BYTEORDER)
    payload_bytes = recv_exact(sock, payload_length)
    return length_prefix + payload_bytes

