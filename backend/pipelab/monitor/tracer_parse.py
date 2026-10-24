"""Parse GStreamer tracer log records and aggregate them into live statistics.

When a process is launched with ``GST_TRACERS="stats;latency"`` and ``GST_DEBUG=GST_TRACER:7``,
GStreamer writes one log line per traced event. This module turns those lines into the same
``stats`` shape the editor's runtime already streams (per-link throughput, per-element latency,
streaming threads), so the monitor can show a live pipeline flowing with the same panels.

Records we use (the ``stats`` and ``latency`` tracers):

* ``new-element``  ix → element name/type (emitted once, at startup)
* ``new-pad``      ix → pad name + owning element ix
* ``buffer``       one per buffer pushed: src pad/element, peer pad/element, size, pts, thread
* ``element-latency`` time a buffer spent inside one element
* ``latency``      end-to-end time from the source to a sink

Parsing is pure and tolerant: unknown records and malformed fields are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_KINDS = ("new-element", "new-pad", "buffer", "element-latency", "latency")
# A record is "<kind>, k=(type)v, k=(type)v;" somewhere on the log line.
_RECORD = re.compile(r"\b(" + "|".join(_KINDS) + r"), (.*?);")
_FIELD = re.compile(r"([a-z0-9-]+)=\((?P<type>[^)]*)\)(?P<val>[^,;]*)")

_INVALID_IX = 0xFFFFFFFF


def parse_record(line: str) -> tuple[str, dict[str, str]] | None:
    """Return ``(kind, fields)`` for the first known tracer record on ``line``, or ``None``."""
    match = _RECORD.search(line)
    if not match:
        return None
    kind = match.group(1)
    fields = {m.group(1): m.group("val").strip() for m in _FIELD.finditer(match.group(2))}
    # The leading "<kind>," itself looks like no field; ensure we did capture the body.
    return kind, fields


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


@dataclass
class _EdgeAccum:
    buffers: int = 0
    bytes: int = 0
    last_pts: int | None = None


@dataclass
class _ElemAccum:
    total_ns: int = 0
    max_ns: int = 0
    samples: int = 0


@dataclass
class StatsAccumulator:
    """Ingest tracer records and periodically drain aggregated statistics.

    Element/pad index→name maps persist across drains (they are assigned once at startup); the
    per-window counters reset on every :meth:`drain`.
    """

    elements: dict[int, str] = field(default_factory=dict)  # element ix -> name
    pads: dict[int, tuple[str, int]] = field(default_factory=dict)  # pad ix -> (name, element ix)
    _edges: dict[str, _EdgeAccum] = field(default_factory=dict)
    _elem_latency: dict[str, _ElemAccum] = field(default_factory=dict)
    _threads: dict[int, set[str]] = field(default_factory=dict)  # thread id -> edge keys seen
    _end_to_end: _ElemAccum = field(default_factory=_ElemAccum)

    def ingest_line(self, line: str) -> None:
        record = parse_record(line)
        if record is not None:
            self.ingest(*record)

    def ingest(self, kind: str, fields: dict[str, str]) -> None:
        if kind == "new-element":
            ix = _int(fields.get("ix"))
            if ix is not None and ix != _INVALID_IX:
                self.elements[ix] = fields.get("name", str(ix))
        elif kind == "new-pad":
            ix = _int(fields.get("ix"))
            elem_ix = _int(fields.get("parent-ix"))
            if ix is not None and elem_ix is not None:
                self.pads[ix] = (fields.get("name", str(ix)), elem_ix)
        elif kind == "buffer":
            self._ingest_buffer(fields)
        elif kind == "element-latency":
            self._ingest_elem_latency(fields)
        elif kind == "latency":
            self._ingest_latency(fields)

    def _edge_key(
        self, src_elem: int | None, src_pad: int | None, dst_elem: int | None, dst_pad: int | None
    ) -> str | None:
        src = self.elements.get(src_elem) if src_elem is not None else None
        dst = self.elements.get(dst_elem) if dst_elem is not None else None
        if not src or not dst:
            return None
        src_pad_name = self.pads.get(src_pad, (str(src_pad), 0))[0] if src_pad is not None else "?"
        dst_pad_name = self.pads.get(dst_pad, (str(dst_pad), 0))[0] if dst_pad is not None else "?"
        return f"{src}:{src_pad_name}>{dst}:{dst_pad_name}"

    def _ingest_buffer(self, fields: dict[str, str]) -> None:
        key = self._edge_key(
            _int(fields.get("element-ix")),
            _int(fields.get("pad-ix")),
            _int(fields.get("peer-element-ix")),
            _int(fields.get("peer-pad-ix")),
        )
        if key is None:
            return
        accum = self._edges.setdefault(key, _EdgeAccum())
        accum.buffers += 1
        accum.bytes += _int(fields.get("buffer-size")) or 0
        if fields.get("have-buffer-pts") in ("1", "true", "True"):
            accum.last_pts = _int(fields.get("buffer-pts"))
        thread = _int(fields.get("thread-id"))
        if thread is not None:
            self._threads.setdefault(thread, set()).add(key)

    def _ingest_elem_latency(self, fields: dict[str, str]) -> None:
        name = fields.get("element")
        time_ns = _int(fields.get("time"))
        if not name or time_ns is None:
            return
        accum = self._elem_latency.setdefault(name, _ElemAccum())
        accum.total_ns += time_ns
        accum.max_ns = max(accum.max_ns, time_ns)
        accum.samples += 1

    def _ingest_latency(self, fields: dict[str, str]) -> None:
        time_ns = _int(fields.get("time"))
        if time_ns is None:
            return
        self._end_to_end.total_ns += time_ns
        self._end_to_end.max_ns = max(self._end_to_end.max_ns, time_ns)
        self._end_to_end.samples += 1

    def drain(self, window_seconds: float) -> dict:
        """Return aggregated stats over the ingested records and reset the per-window counters.

        Edges are keyed by ``"srcElement:srcPad>dstElement:dstPad"`` and elements by name; the live
        session translates those to node and edge ids. ``window_seconds`` turns counts into rates.
        """
        window = max(window_seconds, 1e-3)
        edges = {
            key: {
                "buffers": a.buffers,
                "bytes": a.bytes,
                "fps": round(a.buffers / window, 2),
                "bitrate": round(a.bytes * 8 / window, 1),
                "pts": a.last_pts / 1e9 if a.last_pts is not None else None,
            }
            for key, a in self._edges.items()
        }
        elements = {
            name: {
                "avg_ms": round(a.total_ns / a.samples / 1e6, 3),
                "max_ms": round(a.max_ns / 1e6, 3),
                "samples": a.samples,
            }
            for name, a in self._elem_latency.items()
            if a.samples
        }
        threads = [{"id": tid, "edges": sorted(keys)} for tid, keys in self._threads.items()]
        end_to_end = None
        if self._end_to_end.samples:
            end_to_end = {
                "avg_ms": round(self._end_to_end.total_ns / self._end_to_end.samples / 1e6, 3),
                "max_ms": round(self._end_to_end.max_ns / 1e6, 3),
                "samples": self._end_to_end.samples,
            }

        self._edges.clear()
        self._elem_latency.clear()
        self._threads.clear()
        self._end_to_end = _ElemAccum()
        return {"edges": edges, "elements": elements, "threads": threads, "end_to_end": end_to_end}
