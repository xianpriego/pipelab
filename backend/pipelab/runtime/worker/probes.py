"""Link probes: record the buffers and events crossing a link.

Records are collected from the streaming thread and sent in batches by the
main loop, capped so that a 1000 packets/s RTP link cannot flood the UI.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from pipelab.gst import Gst

Emit = Callable[[dict[str, Any]], None]
MAX_BATCH = 100
_PROBE_TYPES = Gst.PadProbeType.BUFFER | Gst.PadProbeType.BUFFER_LIST | Gst.PadProbeType.EVENT_DOWNSTREAM
_OFFSET_NONE = 0xFFFFFFFFFFFFFFFF
_DETAIL_LIMIT = 400


def _seconds(value: int) -> float | None:
    return None if value == Gst.CLOCK_TIME_NONE else round(value / Gst.SECOND, 6)


def buffer_record(buffer: Gst.Buffer, now: float) -> dict[str, Any]:
    flags = list(getattr(buffer.get_flags(), "value_nicks", None) or [])
    return {
        "kind": "buffer",
        "time": now,
        "pts": _seconds(buffer.pts),
        "dts": _seconds(buffer.dts),
        "duration": _seconds(buffer.duration),
        "size": buffer.get_size(),
        "flags": flags,
        "offset": None if buffer.offset == _OFFSET_NONE else buffer.offset,
    }


def _segment_detail(event: Gst.Event) -> str:
    segment = event.parse_segment()
    return (
        f"format={segment.format.value_nick} rate={segment.rate} start={_seconds(segment.start)} "
        f"stop={_seconds(segment.stop)} time={_seconds(segment.time)} base={_seconds(segment.base)}"
    )


def event_record(event: Gst.Event, now: float) -> dict[str, Any]:
    if event.type == Gst.EventType.CAPS:
        detail = event.parse_caps().to_string()
    elif event.type == Gst.EventType.SEGMENT:
        detail = _segment_detail(event)
    elif event.type == Gst.EventType.TAG:
        detail = event.parse_tag().to_string()
    else:
        structure = event.get_structure()
        detail = structure.to_string() if structure is not None else ""
    return {
        "kind": "event",
        "time": now,
        "event": Gst.EventType.get_name(event.type),
        "detail": detail[:_DETAIL_LIMIT],
    }


class LinkProbe:
    def __init__(self, edge_id: str, pad: Gst.Pad, started: float, emit: Emit) -> None:
        self._edge_id = edge_id
        self._pad = pad
        self._started = started
        self._emit = emit
        self._items: list[dict[str, Any]] = []
        self._dropped = 0
        self._lock = threading.Lock()
        self._probe = pad.add_probe(_PROBE_TYPES, self._on_probe)

    def _record(self, item: dict[str, Any]) -> None:
        with self._lock:
            if len(self._items) < MAX_BATCH:
                self._items.append(item)
            else:
                self._dropped += 1

    def _on_probe(self, _pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        now = round(time.monotonic() - self._started, 3)
        if info.type & Gst.PadProbeType.BUFFER:
            self._record(buffer_record(info.get_buffer(), now))
        elif info.type & Gst.PadProbeType.BUFFER_LIST:
            buffers = info.get_buffer_list()
            for index in range(buffers.length()):
                self._record(buffer_record(buffers.get(index), now))
        elif info.type & Gst.PadProbeType.EVENT_DOWNSTREAM:
            self._record(event_record(info.get_event(), now))
        return Gst.PadProbeReturn.OK

    def flush(self) -> None:
        with self._lock:
            items, dropped = self._items, self._dropped
            self._items, self._dropped = [], 0
        if items or dropped:
            self._emit({"type": "probe", "edge_id": self._edge_id, "items": items, "dropped": dropped})

    def close(self) -> None:
        self._pad.remove_probe(self._probe)
        self.flush()
