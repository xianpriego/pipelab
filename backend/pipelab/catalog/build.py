"""Supervises the catalog describe worker subprocess, surviving crashing elements."""

from __future__ import annotations

import hashlib
import json
import queue
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from pipelab.catalog.models import CatalogData, ElementInfo
from pipelab.gst import Gst

CATALOG_SCHEMA_VERSION = 5

ProgressCallback = Callable[[int, int], None]


def registry_hash() -> str:
    """Fingerprint of the installed element factories (changes with plugins/GPUs)."""
    digest = hashlib.sha256(f"{CATALOG_SCHEMA_VERSION}:{Gst.version_string()}".encode())
    features = Gst.Registry.get().get_feature_list(Gst.ElementFactory)
    for factory in sorted(features, key=lambda f: f.get_name()):
        digest.update(f"{factory.get_name()}:{factory.get_plugin_name()}:{factory.get_rank()};".encode())
    return digest.hexdigest()[:16]


def _read_lines(stream, timeout: float) -> Iterator[str | None]:
    """Yield lines from ``stream``; ``None`` signals a timeout."""
    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        for line in stream:
            lines.put(line)
        lines.put("")

    threading.Thread(target=pump, daemon=True).start()
    while True:
        try:
            line = lines.get(timeout=timeout)
        except queue.Empty:
            yield None
            return
        if line == "":
            return
        yield line


@dataclass
class _BuildState:
    elements: dict[str, ElementInfo] = field(default_factory=dict)
    no_instantiate: set[str] = field(default_factory=set)
    skipped: list[str] = field(default_factory=list)
    last_done: str | None = None
    total: int = 0


def _run_worker(state: _BuildState, timeout: float, progress: ProgressCallback) -> bool:
    """Run one describe worker process. Returns True when it reached the end."""
    command = [sys.executable, "-m", "pipelab.catalog.describe_worker"]
    if state.last_done:
        command += ["--after", state.last_done]
    if state.no_instantiate:
        command += ["--no-instantiate", ",".join(sorted(state.no_instantiate))]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    current: str | None = None
    try:
        for line in _read_lines(process.stdout, timeout):
            if line is None:
                break
            event = json.loads(line)
            kind = event["event"]
            if kind == "total":
                state.total = event["count"]
            elif kind == "begin":
                current = event["name"]
            elif kind == "element":
                info = ElementInfo.model_validate(event["data"])
                state.elements[info.name] = info
                state.last_done, current = info.name, None
                progress(len(state.elements), state.total)
            elif kind == "failed":
                state.skipped.append(event["name"])
                state.last_done, current = event["name"], None
            elif kind == "done":
                return True
    finally:
        process.kill()
        process.wait()
    _handle_failure(state, current)
    return False


def _handle_failure(state: _BuildState, current: str | None) -> None:
    if current is None:
        raise RuntimeError("the catalog describe worker exited before describing any element")
    if current in state.no_instantiate:
        state.skipped.append(current)
        state.last_done = current
    else:
        state.no_instantiate.add(current)


def build_catalog(timeout: float = 30.0, progress: ProgressCallback | None = None) -> CatalogData:
    state = _BuildState()
    report = progress or (lambda _done, _total: None)
    while not _run_worker(state, timeout, report):
        pass
    return CatalogData(
        gstreamer_version=Gst.version_string(),
        registry_hash=registry_hash(),
        elements=sorted(state.elements.values(), key=lambda e: e.name),
        skipped=state.skipped,
    )
