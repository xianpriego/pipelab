"""Live statistics for a monitored pipeline, by tailing its GStreamer tracer log.

A process launched with ``GST_TRACERS`` and ``GST_DEBUG_FILE`` writes tracer records to a log file.
:class:`LiveMonitor` tails that file (reached through ``/proc/<pid>/root`` so logs inside other
containers work) and, on each poll, aggregates the records written since the previous poll into the
same ``stats`` shape the editor streams: per-link throughput, per-element latency, and the streaming
threads with their CPU. The poll interval is the measurement window.

State per pid (file offset, the element/pad index maps, thread CPU baselines) is kept in memory so
successive polls measure only the new interval. The first poll scans the file once to learn the
element/pad names assigned at startup, then tails forward.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from pipelab.monitor.discover import _PROC
from pipelab.monitor.dump import _resolve_in_target
from pipelab.monitor.models import MonitorPipeline
from pipelab.monitor.tracer_parse import StatsAccumulator

# Cap the one-time startup scan so a huge pre-existing log cannot stall the first poll.
_STARTUP_SCAN_BYTES = 64 * 1024 * 1024
_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


@dataclass
class _LiveState:
    log_path: Path
    accum: StatsAccumulator
    offset: int = 0
    last_poll: float = 0.0
    inode: int | None = None
    cpu_baseline: dict[int, tuple[int, float]] = field(default_factory=dict)  # tid -> (ticks, wall)


class LiveMonitor:
    """Per-process tracer-log tailers, keyed by pid."""

    def __init__(self) -> None:
        self._states: dict[int, _LiveState] = {}
        # pid -> (element name -> node id, edge key -> edge id), from the latest snapshot. Kept
        # apart from the tailer state so it can be set before the first poll attaches a tailer.
        self._structures: dict[int, tuple[dict[str, str], dict[str, str]]] = {}

    def forget(self, pid: int) -> None:
        self._states.pop(pid, None)
        self._structures.pop(pid, None)

    def attach(self, pid: int, log_path: Path) -> _LiveState:
        state = self._states.get(pid)
        try:
            stat = log_path.stat()
        except OSError:
            stat = None
        if state is None or state.log_path != log_path or (stat and state.inode != stat.st_ino):
            state = _LiveState(log_path=log_path, accum=StatsAccumulator())
            state.inode = stat.st_ino if stat else None
            self._scan_startup(state)
            self._states[pid] = state
        return state

    def _scan_startup(self, state: _LiveState) -> None:
        """Read the file once to learn element/pad index→name maps, then point at its end."""
        try:
            with state.log_path.open("r", errors="replace") as handle:
                read = 0
                for line in handle:
                    read += len(line)
                    if "new-element" in line or "new-pad" in line:
                        state.accum.ingest_line(line)
                    if read > _STARTUP_SCAN_BYTES:
                        handle.seek(0, os.SEEK_END)
                        break
                state.offset = handle.tell()
        except OSError:
            state.offset = 0
        state.last_poll = time.monotonic()

    def set_structure(self, pid: int, pipeline: MonitorPipeline) -> None:
        """Teach the tailer how to translate element/pad names into this snapshot's ids."""
        node_ids = {node.name: node.id for node in pipeline.nodes}
        by_id = {node.id: node.name for node in pipeline.nodes}
        edge_ids: dict[str, str] = {}
        for edge in pipeline.edges:
            src = by_id.get(edge.source)
            dst = by_id.get(edge.target)
            if src and dst:
                edge_ids[f"{src}:{edge.source_pad}>{dst}:{edge.target_pad}"] = edge.id
        self._structures[pid] = (node_ids, edge_ids)

    def poll(self, pid: int, log_path: Path) -> dict:
        """Read new tracer records and return a ``stats``-shaped dict for the elapsed interval."""
        state = self.attach(pid, log_path)
        now = time.monotonic()
        window = max(now - state.last_poll, 1e-3)
        state.last_poll = now

        self._read_new(state)
        raw = state.accum.drain(window)
        return self._translate(pid, state, raw, window)

    def _read_new(self, state: _LiveState) -> None:
        try:
            size = state.log_path.stat().st_size
            if size < state.offset:  # truncated / rotated
                state.offset = 0
            with state.log_path.open("r", errors="replace") as handle:
                handle.seek(state.offset)
                for line in handle:
                    state.accum.ingest_line(line)
                state.offset = handle.tell()
        except OSError:
            pass

    def _translate(self, pid: int, state: _LiveState, raw: dict, window: float) -> dict:
        node_ids, edge_ids_map = self._structures.get(pid, ({}, {}))
        edges = {edge_ids_map[key]: value for key, value in raw["edges"].items() if key in edge_ids_map}
        elements = {node_ids[name]: value for name, value in raw["elements"].items() if name in node_ids}
        threads = []
        for thread in raw["threads"]:
            edge_ids = [edge_ids_map[k] for k in thread["edges"] if k in edge_ids_map]
            threads.append(
                {
                    "id": thread["id"],
                    "name": _thread_name(pid, thread["id"]),
                    "cpu": self._thread_cpu(pid, state, thread["id"], window),
                    "edges": edge_ids,
                }
            )
        return {
            "type": "stats",
            "time": time.time(),
            "edges": edges,
            "elements": elements,
            "threads": threads,
            "end_to_end": raw["end_to_end"],
        }

    def _thread_cpu(self, pid: int, state: _LiveState, tid: int, window: float) -> float | None:
        ticks = _thread_ticks(pid, tid)
        if ticks is None:
            return None
        now = time.monotonic()
        prev = state.cpu_baseline.get(tid)
        state.cpu_baseline[tid] = (ticks, now)
        if prev is None:
            return None
        dt = now - prev[1]
        if dt <= 0:
            return None
        return round((ticks - prev[0]) / _CLK_TCK / dt * 100, 1)


def _thread_ticks(pid: int, tid: int) -> int | None:
    try:
        stat = (_PROC / str(pid) / "task" / str(tid) / "stat").read_text()
    except OSError:
        return None
    # utime (14) + stime (15); fields are after the parenthesised comm, which may contain spaces.
    after = stat.rpartition(")")[2].split()
    try:
        return int(after[11]) + int(after[12])
    except (IndexError, ValueError):
        return None


def _thread_name(pid: int, tid: int) -> str:
    try:
        return (_PROC / str(pid) / "task" / str(tid) / "comm").read_text().strip() or str(tid)
    except OSError:
        return str(tid)


def resolve_tracer_log(pid: int, log_path: str) -> Path | None:
    """Map the target's ``GST_DEBUG_FILE`` path into one we can read, if it exists."""
    resolved = _resolve_in_target(pid, log_path)
    return resolved if resolved.exists() else None
