"""Monitor pipelines running live on the machine, read-only.

Unlike the rest of the API, which designs and runs *our* pipelines, these endpoints observe
pipelines owned by other processes — a command-line ``gst-launch``, an app written in C, Rust or
Python, possibly inside another container — and reconstruct them as a graph for inspection. Nothing
here can modify the observed pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pipelab.api.services import Services, get_services
from pipelab.monitor.discover import describe_process, discover
from pipelab.monitor.dot_parse import parse_dot
from pipelab.monitor.dump import DumpError, dump_process
from pipelab.monitor.graph_map import build_gtype_index, to_monitor_pipeline
from pipelab.monitor.live import resolve_tracer_log
from pipelab.monitor.models import MonitorPipeline, MonitorProcess, MonitorSource

router = APIRouter()
ServicesDep = Annotated[Services, Depends(get_services)]


class SnapshotRequest(BaseModel):
    pid: int
    method: Literal["auto", "dot-dir", "gdb"] = "auto"


@router.get("/monitor/processes")
def processes() -> dict[str, list[MonitorProcess]]:
    """List GStreamer processes visible to the API (see the monitor docs for cross-container use)."""
    return {"processes": discover()}


@router.post("/monitor/snapshot")
def snapshot(request: SnapshotRequest, services: ServicesDep) -> MonitorPipeline:
    """Reconstruct the graph of the pipeline running in process ``pid``."""
    process = describe_process(request.pid)
    if process is None:
        raise HTTPException(404, f"No GStreamer process with pid {request.pid} is visible.")
    try:
        dot_text, method = dump_process(request.pid, process.dot_dir, request.method)
    except DumpError as exc:
        raise HTTPException(409, str(exc)) from exc

    parsed = parse_dot(dot_text)
    if not parsed.elements:
        raise HTTPException(422, "The pipeline graph could not be parsed from the process dump.")

    index = _gtype_index(services)
    source = MonitorSource(
        pid=process.pid,
        cmdline=process.cmdline,
        process=process.process,
        container=process.container,
        runtime=process.runtime,
        method=method,  # type: ignore[arg-type]
        captured_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    pipeline = to_monitor_pipeline(parsed, source, index)
    # Teach the live tailer this snapshot's ids so subsequent /monitor/live polls can be mapped.
    services.live_monitor.set_structure(request.pid, pipeline)
    return pipeline


@router.get("/monitor/live")
def live(pid: int, services: ServicesDep) -> dict:
    """Live statistics for a monitored pipeline over the interval since the previous call.

    Returns `{available: false, reason}` when the process was not launched with the GStreamer
    tracers (`GST_TRACERS` + `GST_DEBUG=GST_TRACER:7` + a readable `GST_DEBUG_FILE`); otherwise a
    `stats`-shaped payload keyed by the ids of the latest snapshot.
    """
    process = describe_process(pid)
    if process is None:
        raise HTTPException(404, f"No GStreamer process with pid {pid} is visible.")
    if not process.full_stats or not process.tracer_log:
        return {
            "available": False,
            "reason": (
                "This pipeline was not launched with the GStreamer tracers. For live statistics, "
                'start it with GST_TRACERS="stats;latency", GST_DEBUG=GST_TRACER:7 and a readable '
                "GST_DEBUG_FILE."
            ),
            "tracers": process.tracers,
        }
    log_path = resolve_tracer_log(pid, process.tracer_log)
    if log_path is None:
        return {"available": False, "reason": "The tracer log file is not readable from the API."}
    stats = services.live_monitor.poll(pid, log_path)
    stats["available"] = True
    return stats


def _gtype_index(services: Services) -> dict[str, str]:
    """GObject-type → factory map from the catalog, if the catalog is ready; empty otherwise so the
    monitor still works (nodes then fall back to a best-effort factory guess)."""
    try:
        return build_gtype_index(services.catalog.catalog.elements)
    except Exception:  # noqa: BLE001 - the monitor must work even while the catalog is unavailable
        return {}
