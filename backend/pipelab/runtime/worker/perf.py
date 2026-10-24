"""Where time goes in a running pipeline: element latency, streaming threads and queue levels.

* Latency: the link monitor stamps every buffer crossing a link with its PTS. When an element
  pushes a buffer whose PTS entered it on one of its input links, the difference is the time it
  spent inside (processing, or waiting in a queue). Elements that rewrite timestamps (rate
  changers, some muxers) are simply not measured.
* Threads: the thread pushing each link (its streaming thread) and its CPU usage from /proc.
* Queues: fill level of every queue/queue2 and how often it overran (full, or dropping when
  leaky) or ran dry.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from pipelab.gst import GObject, Gst

_RECENT = 128  # PTS remembered per link: enough for decoder reordering and queue depths
_QUEUES = {"queue", "queue2"}
_CLOCK_TICKS = os.sysconf("SC_CLK_TCK")


@dataclass
class Arrivals:
    """Recent PTS → arrival time (ns) on one link."""

    times: OrderedDict[int, int] = field(default_factory=OrderedDict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, pts: int, now: int) -> None:
        with self.lock:
            self.times[pts] = now
            if len(self.times) > _RECENT:
                self.times.popitem(last=False)

    def get(self, pts: int) -> int | None:
        with self.lock:
            return self.times.get(pts)


@dataclass
class _Window:
    total: int = 0
    count: int = 0
    peak: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, value: int) -> None:
        with self.lock:
            self.total += value
            self.count += 1
            self.peak = max(self.peak, value)

    def take(self) -> dict[str, float] | None:
        with self.lock:
            if not self.count:
                return None
            report = {
                "avg_ms": round(self.total / self.count / 1e6, 3),
                "max_ms": round(self.peak / 1e6, 3),
                "samples": self.count,
            }
            self.total = self.count = self.peak = 0
            return report


@dataclass
class LinkTiming:
    """What one link contributes: arrivals into its target, latency samples of its source."""

    arrivals: Arrivals
    source_inputs: dict[str, Arrivals]  # input links of the source element (shared, filled later)
    window: _Window

    def on_buffer(self, pts: int, now: int) -> None:
        self.arrivals.add(pts, now)
        for inputs in list(self.source_inputs.values()):
            entered = inputs.get(pts)
            if entered is not None and entered <= now:
                self.window.add(now - entered)
                return


class LatencyTracker:
    def __init__(self) -> None:
        self._inputs: dict[str, dict[str, Arrivals]] = {}  # node id → {edge id: arrivals into it}
        self._windows: dict[str, _Window] = {}

    def link(self, edge_id: str, source: str, target: str) -> LinkTiming:
        arrivals = Arrivals()
        self._inputs.setdefault(target, {})[edge_id] = arrivals
        window = self._windows.setdefault(source, _Window())
        return LinkTiming(arrivals, self._inputs.setdefault(source, {}), window)

    def detach_prefix(self, prefix: str) -> None:
        for node in [n for n in self._windows if n.startswith(prefix)]:
            del self._windows[node]
        for node, inputs in list(self._inputs.items()):
            if node.startswith(prefix):
                del self._inputs[node]
            else:
                for edge_id in [e for e in inputs if e.startswith(prefix)]:
                    del inputs[edge_id]

    def snapshot(self) -> dict[str, dict[str, float]]:
        reports = {node: window.take() for node, window in self._windows.items()}
        return {node: report for node, report in reports.items() if report is not None}


class ThreadUsage:
    """CPU of the streaming threads seen on the links, from /proc/self/task/<tid>/stat."""

    def __init__(self) -> None:
        self._ticks: dict[int, int] = {}
        self._last = time.monotonic()

    def snapshot(self, edges_by_thread: dict[int, list[str]]) -> list[dict[str, Any]]:
        now = time.monotonic()
        elapsed = max(now - self._last, 1e-3)
        self._last = now
        threads = []
        for tid, edges in sorted(edges_by_thread.items()):
            usage = _read_thread(tid)
            if usage is None:
                self._ticks.pop(tid, None)
                continue
            name, ticks = usage
            previous = self._ticks.get(tid)
            self._ticks[tid] = ticks
            cpu = None if previous is None else round((ticks - previous) / _CLOCK_TICKS / elapsed * 100, 1)
            threads.append({"id": tid, "name": name, "cpu": cpu, "edges": sorted(edges)})
        return threads


def _read_thread(tid: int) -> tuple[str, int] | None:
    try:
        with open(f"/proc/self/task/{tid}/stat") as stat:
            text = stat.read()
    except OSError:
        return None
    # "tid (comm) state ..." where comm may contain spaces and parentheses.
    name = text[text.index("(") + 1 : text.rindex(")")]
    fields = text[text.rindex(")") + 2 :].split()
    return name, int(fields[11]) + int(fields[12])  # utime + stime


@dataclass
class _QueueCounters:
    element: Gst.Element
    overruns: int = 0
    underruns: int = 0


class QueueLevels:
    def __init__(self) -> None:
        self._queues: dict[str, _QueueCounters] = {}

    def watch(self, node_id: str, factory: str, element: Gst.Element) -> None:
        if factory not in _QUEUES or node_id in self._queues:
            return
        counters = _QueueCounters(element)
        self._queues[node_id] = counters
        # queue has these signals, queue2 does not (its level is still reported).
        if GObject.signal_lookup("overrun", type(element)):
            element.connect("overrun", lambda _queue: setattr(counters, "overruns", counters.overruns + 1))
            element.connect("underrun", lambda _queue: setattr(counters, "underruns", counters.underruns + 1))

    def detach_prefix(self, prefix: str) -> None:
        for node_id in [n for n in self._queues if n.startswith(prefix)]:
            del self._queues[node_id]

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        return {node_id: _queue_level(counters) for node_id, counters in self._queues.items()}


def _queue_level(counters: _QueueCounters) -> dict[str, float | int]:
    queue = counters.element
    level = {
        "buffers": queue.get_property("current-level-buffers"),
        "bytes": queue.get_property("current-level-bytes"),
        "time_ms": round(queue.get_property("current-level-time") / 1e6, 1),
        "max_buffers": queue.get_property("max-size-buffers"),
        "max_bytes": queue.get_property("max-size-bytes"),
        "max_time_ms": round(queue.get_property("max-size-time") / 1e6, 1),
    }
    # The fullest of the enabled limits (0 disables a limit).
    ratios = [
        level[current] / level[limit]
        for current, limit in (("buffers", "max_buffers"), ("bytes", "max_bytes"), ("time_ms", "max_time_ms"))
        if level[limit]
    ]
    return {
        **level,
        "fill": round(min(max(ratios, default=0.0), 1.0), 3),
        "overruns": counters.overruns,
        "underruns": counters.underruns,
    }
