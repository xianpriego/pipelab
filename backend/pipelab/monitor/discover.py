"""Find processes on the machine that are running GStreamer pipelines.

A process is a candidate when ``libgstreamer-1.0.so`` is mapped into it. For each candidate we
gather what we need to pull a pipeline graph out of it later: its command line, whether it lives
in a container, and whether it was launched with ``GST_DEBUG_DUMP_DOT_DIR`` (which lets us read
its graph dumps without touching the process).

Everything degrades gracefully: ``/proc`` entries for other users may be unreadable, so each read
is guarded and a candidate is reported with whatever could be gathered.

To see processes outside this container, run the API with the host PID namespace and ``/proc``
mounted (see ``docs/`` / the monitor API). Without that, only processes in this namespace show up.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from pipelab.monitor.models import MonitorProcess

_PROC = Path(os.environ.get("PIPELAB_PROC", "/proc"))
_GST_LIB = re.compile(r"libgstreamer-1\.0\.so")
_CONTAINER = re.compile(r"(?:docker[-/]|libpod-|containerd.*cri-containerd[-:])([0-9a-f]{12,64})")


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except (OSError, PermissionError):
        return ""


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except (OSError, PermissionError):
        return b""


def _uses_gstreamer(pid: int) -> bool:
    maps = _read(_PROC / str(pid) / "maps")
    if maps:
        return bool(_GST_LIB.search(maps))
    # maps unreadable (another user): fall back to the mapped-files dir listing names only.
    try:
        for entry in (_PROC / str(pid) / "map_files").iterdir():
            target = os.readlink(entry) if entry.is_symlink() else str(entry)
            if _GST_LIB.search(target):
                return True
    except (OSError, PermissionError):
        return False
    return False


def _cmdline(pid: int) -> str:
    raw = _read_bytes(_PROC / str(pid) / "cmdline")
    if not raw:
        return _read(_PROC / str(pid) / "comm").strip()
    return " ".join(part for part in raw.decode("utf-8", "replace").split("\0") if part)


def _environ(pid: int) -> dict[str, str]:
    raw = _read_bytes(_PROC / str(pid) / "environ")
    env: dict[str, str] = {}
    for item in raw.decode("utf-8", "replace").split("\0"):
        key, sep, value = item.partition("=")
        if sep:
            env[key] = value
    return env


def _container(pid: int) -> str | None:
    cgroup = _read(_PROC / str(pid) / "cgroup")
    match = _CONTAINER.search(cgroup)
    if match:
        return match.group(1)[:12]
    return None


def _owner(pid: int) -> str:
    try:
        uid = (_PROC / str(pid)).stat().st_uid
    except OSError:
        return ""
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name
    except (KeyError, ImportError):
        return str(uid)


def _pids() -> list[int]:
    pids = []
    try:
        for entry in _PROC.iterdir():
            if entry.name.isdigit():
                pids.append(int(entry.name))
    except OSError:
        pass
    return sorted(pids)


def describe_process(pid: int) -> MonitorProcess | None:
    """Return a :class:`MonitorProcess` for ``pid`` if it is running GStreamer, else ``None``."""
    if not (_PROC / str(pid)).exists() or not _uses_gstreamer(pid):
        return None
    cmdline = _cmdline(pid)
    env = _environ(pid)
    dot_dir = env.get("GST_DEBUG_DUMP_DOT_DIR") or None
    container = _container(pid)
    methods: list[str] = []
    if dot_dir:
        methods.append("dot-dir")
    methods.append("gdb")
    tracers, tracer_log, full_stats = _stats_capability(pid, env)
    return MonitorProcess(
        pid=pid,
        cmdline=cmdline,
        process=os.path.basename(cmdline.split(" ", 1)[0]) if cmdline else "",
        container=container,
        runtime="docker" if container else "native",
        user=_owner(pid),
        methods=methods,  # type: ignore[arg-type]
        dot_dir=dot_dir,
        is_pipelab="pipelab.runtime.worker" in cmdline,
        tracers=tracers,
        tracer_log=tracer_log,
        full_stats=full_stats,
    )


def _stats_capability(pid: int, env: dict[str, str]) -> tuple[list[str], str | None, bool]:
    """Decide whether we can tail this process's tracer log for live statistics.

    Needs ``GST_TRACERS`` (at least ``stats``), the ``GST_TRACER`` debug category enabled, and a
    ``GST_DEBUG_FILE`` we can actually read (resolved through ``/proc/<pid>/root``).
    """
    raw_tracers = env.get("GST_TRACERS", "")
    tracers = [t.split("(", 1)[0].strip() for t in raw_tracers.split(";") if t.strip()]
    log = env.get("GST_DEBUG_FILE") or None
    debug = env.get("GST_DEBUG", "")
    tracer_debug_on = "GST_TRACER" in debug or debug.strip() in ("*:7", "7")
    readable_log = None
    if log and tracer_debug_on:
        from pipelab.monitor.dump import _resolve_in_target

        resolved = _resolve_in_target(pid, log)
        if resolved.exists():
            readable_log = log
    full_stats = bool(tracers) and "stats" in tracers and readable_log is not None
    return tracers, readable_log, full_stats


def discover(include_self: bool = False) -> list[MonitorProcess]:
    """List every GStreamer process visible in the current PID namespace."""
    me = os.getpid()
    found: list[MonitorProcess] = []
    for pid in _pids():
        if pid == me and not include_self:
            continue
        try:
            process = describe_process(pid)
        except Exception:  # noqa: BLE001 - a process racing away mid-scan must not abort discovery
            process = None
        if process is not None:
            found.append(process)
    return found
