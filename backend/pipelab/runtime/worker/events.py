"""Events the worker sends to the API (see ``channel.py`` for the framing)."""

from __future__ import annotations

from typing import Any, Protocol


class Emit(Protocol):
    """Sends one event; ``payload`` carries binary data (preview frames)."""

    def __call__(self, event: dict[str, Any], payload: bytes = b"", /) -> None: ...


def bus_event(
    kind: str, text: str, source: str | None = None, node_id: str | None = None, **extra: Any
) -> dict[str, Any]:
    """A bus-like message produced by the worker itself (not by a GStreamer element)."""
    return {"type": "bus", "kind": kind, "source": source, "node_id": node_id, "text": text, **extra}
