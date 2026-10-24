"""Framing shared by the API and the pipeline worker process.

Worker → API (stdout): ``u32 header_len | u32 payload_len | header JSON | payload``.
API → browser (WebSocket binary): ``u32 header_len | header JSON | payload``.
API → worker (stdin): one JSON command per line.
"""

from __future__ import annotations

import asyncio
import json
import struct
from typing import Any, BinaryIO

_WORKER_HEADER = struct.Struct(">II")
_WS_HEADER = struct.Struct(">I")


def encode_frame(header: dict[str, Any], payload: bytes = b"") -> bytes:
    data = json.dumps(header, separators=(",", ":")).encode()
    return _WORKER_HEADER.pack(len(data), len(payload)) + data + payload


def write_frame(stream: BinaryIO, header: dict[str, Any], payload: bytes = b"") -> None:
    stream.write(encode_frame(header, payload))
    stream.flush()


async def read_frame(reader: asyncio.StreamReader) -> tuple[dict[str, Any], bytes] | None:
    """Next frame from the worker, ``None`` at end of stream."""
    try:
        sizes = await reader.readexactly(_WORKER_HEADER.size)
        header_len, payload_len = _WORKER_HEADER.unpack(sizes)
        header = json.loads(await reader.readexactly(header_len))
        payload = await reader.readexactly(payload_len) if payload_len else b""
    except asyncio.IncompleteReadError:
        return None
    return header, payload


def encode_ws_binary(header: dict[str, Any], payload: bytes) -> bytes:
    data = json.dumps(header, separators=(",", ":")).encode()
    return _WS_HEADER.pack(len(data)) + data + payload


def decode_ws_binary(frame: bytes) -> tuple[dict[str, Any], bytes]:
    """Inverse of ``encode_ws_binary`` (what the browser does with preview frames)."""
    (size,) = _WS_HEADER.unpack_from(frame)
    start = _WS_HEADER.size
    return json.loads(frame[start : start + size]), frame[start + size :]


def encode_command(command: dict[str, Any]) -> bytes:
    return (json.dumps(command) + "\n").encode()
