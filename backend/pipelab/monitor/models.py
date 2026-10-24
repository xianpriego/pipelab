"""Read-only models describing a live pipeline discovered on the machine.

These are intentionally separate from the editable :mod:`pipelab.graph.models`: a monitored
pipeline is observed, not designed, so it carries extra observed facts (element state, negotiated
caps, GObject type, bin nesting) and no editing affordances.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ElementState = Literal["null", "ready", "paused", "playing", "void-pending"]


class MonitorNode(BaseModel):
    id: str  # stable within this snapshot (the GstObject address)
    name: str  # GStreamer element name
    gtype: str  # GObject type name, e.g. "GstX264Enc"
    factory: str = ""  # resolved factory name, "" if unknown on this machine
    factory_known: bool = False  # the factory exists in this machine's catalog
    state: ElementState | None = None
    is_bin: bool = False  # it contains other elements (a GstBin / component-like)
    parent: str | None = None  # id of the enclosing bin, or None at the top
    properties: dict[str, str] = Field(default_factory=dict)  # observed, as text
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


class MonitorEdge(BaseModel):
    id: str
    source: str  # node id
    source_pad: str
    target: str
    target_pad: str
    caps: str | None = None  # negotiated caps on the link, if any


class MonitorSource(BaseModel):
    """Where a snapshot came from and how it was obtained."""

    pid: int | None = None
    cmdline: str = ""
    process: str = ""  # argv[0] basename
    container: str | None = None  # docker/podman container id or name, if any
    runtime: Literal["native", "docker", "podman"] = "native"
    method: Literal["gdb", "dot-dir", "signal", "file"] = "file"
    captured_at: str = ""  # ISO timestamp


class MonitorPipeline(BaseModel):
    name: str
    source: MonitorSource
    nodes: list[MonitorNode] = Field(default_factory=list)
    edges: list[MonitorEdge] = Field(default_factory=list)


class MonitorProcess(BaseModel):
    """A process on the machine that has GStreamer loaded (a monitoring candidate)."""

    pid: int
    cmdline: str = ""
    process: str = ""
    container: str | None = None
    runtime: Literal["native", "docker", "podman"] = "native"
    user: str = ""
    # How we could obtain a graph from it, best first.
    methods: list[Literal["gdb", "dot-dir"]] = Field(default_factory=list)
    dot_dir: str | None = None  # value of GST_DEBUG_DUMP_DOT_DIR, if set
    is_pipelab: bool = False  # one of our own worker processes
