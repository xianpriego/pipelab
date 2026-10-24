"""Per-link statistics (buffers, fps, bitrate) and negotiated caps."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipelab.gst import Gst
from pipelab.runtime.worker.perf import LatencyTracker, LinkTiming

Emit = Callable[[dict[str, Any]], None]
_PROBE_TYPES = Gst.PadProbeType.BUFFER | Gst.PadProbeType.BUFFER_LIST


@dataclass
class _Counter:
    buffers: int = 0
    bytes: int = 0
    last_pts: int | None = None
    reported_buffers: int = 0
    reported_bytes: int = 0
    thread: int | None = None  # native id of the streaming thread pushing the link
    timing: LinkTiming | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class LinkMonitor:
    def __init__(self, emit: Emit) -> None:
        self._emit = emit
        self._counters: dict[str, _Counter] = {}
        self._last_report = time.monotonic()
        self.latency = LatencyTracker()

    def attach(
        self, edge_id: str, src_pad: Gst.Pad, source: str | None = None, target: str | None = None
    ) -> None:
        """``source``/``target`` (global node ids) enable latency measurements of the source."""
        counter = self._counters.setdefault(edge_id, _Counter())
        if source is not None and target is not None:
            counter.timing = self.latency.link(edge_id, source, target)
        src_pad.add_probe(_PROBE_TYPES, self._on_data, counter)
        src_pad.connect("notify::caps", self._on_caps, edge_id)

    def detach_prefix(self, prefix: str) -> None:
        """Forget the links of a removed instance."""
        for edge_id in [e for e in self._counters if e.startswith(prefix)]:
            del self._counters[edge_id]
        self.latency.detach_prefix(prefix)

    def threads(self) -> dict[int, list[str]]:
        """Streaming thread → links it pushes."""
        by_thread: dict[int, list[str]] = {}
        for edge_id, counter in self._counters.items():
            if counter.thread is not None:
                by_thread.setdefault(counter.thread, []).append(edge_id)
        return by_thread

    def _on_data(self, _pad: Gst.Pad, info: Gst.PadProbeInfo, counter: _Counter) -> Gst.PadProbeReturn:
        buffer = info.get_buffer()
        pts = Gst.CLOCK_TIME_NONE
        with counter.lock:
            counter.thread = threading.get_native_id()
            if buffer is not None:
                counter.buffers += 1
                counter.bytes += buffer.get_size()
                pts = buffer.pts
                if pts != Gst.CLOCK_TIME_NONE:
                    counter.last_pts = pts
            else:
                buffers = info.get_buffer_list()
                if buffers is not None and buffers.length():
                    counter.buffers += buffers.length()
                    counter.bytes += buffers.calculate_size()
                    pts = buffers.get(0).pts
        if counter.timing is not None and pts != Gst.CLOCK_TIME_NONE:
            counter.timing.on_buffer(pts, time.monotonic_ns())
        return Gst.PadProbeReturn.OK

    def _on_caps(self, pad: Gst.Pad, _pspec: Any, edge_id: str) -> None:
        caps = pad.get_current_caps()
        if caps is not None:
            self._emit({"type": "caps", "edge_id": edge_id, "caps": caps.to_string()})

    def snapshot(self) -> dict[str, dict[str, float | int | None]]:
        now = time.monotonic()
        elapsed = max(now - self._last_report, 1e-3)
        self._last_report = now
        stats = {}
        for edge_id, counter in self._counters.items():
            with counter.lock:
                buffers = counter.buffers - counter.reported_buffers
                size = counter.bytes - counter.reported_bytes
                counter.reported_buffers, counter.reported_bytes = counter.buffers, counter.bytes
                stats[edge_id] = {
                    "buffers": counter.buffers,
                    "bytes": counter.bytes,
                    "fps": round(buffers / elapsed, 2),
                    "bitrate": round(size * 8 / elapsed, 1),
                    "pts": counter.last_pts / Gst.SECOND if counter.last_pts is not None else None,
                }
        return stats


def query_time(pipeline: Gst.Pipeline, kind: str) -> float | None:
    query = pipeline.query_position if kind == "position" else pipeline.query_duration
    ok, value = query(Gst.Format.TIME)
    return value / Gst.SECOND if ok and value >= 0 else None
