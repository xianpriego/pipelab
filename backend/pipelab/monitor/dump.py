"""Obtain a ``.dot`` graph from a live process.

Two mechanisms, best first:

* ``dot-dir`` — the process was launched with ``GST_DEBUG_DUMP_DOT_DIR``, so GStreamer has written
  ``.dot`` dumps there (on every state change, and whenever the app asks). We read the newest one.
  The directory is resolved through ``/proc/<pid>/root`` so it is reachable even when the process
  runs inside another container. This needs no cooperation beyond that one environment variable and
  works for pipelines started from the command line or from C, Rust or Python code.

* ``gdb`` — attach to the process and call ``gst_debug_bin_to_dot_data`` on its live pipeline(s)
  (see :mod:`pipelab.monitor.gdb_dump`). This needs no environment variable but does need
  permission to ptrace the target (same user, or ``CAP_SYS_PTRACE`` / root, and a shared PID
  namespace).
"""

from __future__ import annotations

from pathlib import Path

from pipelab.monitor.discover import _PROC

_DOT_SUFFIX = ".dot"


class DumpError(RuntimeError):
    """A graph could not be obtained from the process."""


def _proc_root(pid: int) -> Path:
    return _PROC / str(pid) / "root"


def _resolve_in_target(pid: int, path: str) -> Path:
    """Map a path as the target process sees it into a path we can open (across containers)."""
    rooted = _proc_root(pid) / path.lstrip("/")
    if rooted.exists():
        return rooted
    # Same mount namespace (or /proc/<pid>/root not traversable): try the literal path.
    return Path(path)


def latest_dot(pid: int, dot_dir: str) -> Path | None:
    """The most recently modified ``.dot`` file in the process's dump directory, or ``None``."""
    directory = _resolve_in_target(pid, dot_dir)
    try:
        dots = [p for p in directory.iterdir() if p.suffix == _DOT_SUFFIX]
    except (OSError, PermissionError):
        return None
    if not dots:
        return None
    return max(dots, key=lambda p: p.stat().st_mtime)


def dump_via_dot_dir(pid: int, dot_dir: str) -> str:
    """Return the text of the newest ``.dot`` dump the process has written."""
    dot = latest_dot(pid, dot_dir)
    if dot is None:
        raise DumpError(
            f"No .dot dumps found in {dot_dir!r} for pid {pid}. The process writes one on each "
            "state change; trigger one in the app, or use the gdb method."
        )
    try:
        return dot.read_text(errors="replace")
    except (OSError, PermissionError) as exc:
        raise DumpError(f"Cannot read {dot}: {exc}") from exc


def dump_process(pid: int, dot_dir: str | None, method: str) -> tuple[str, str]:
    """Return ``(dot_text, method_used)`` for ``pid`` using the requested method.

    ``method`` is ``"dot-dir"``, ``"gdb"`` or ``"auto"`` (dot-dir if available, else gdb).
    """
    if method in ("auto", "dot-dir") and dot_dir:
        try:
            return dump_via_dot_dir(pid, dot_dir), "dot-dir"
        except DumpError:
            if method == "dot-dir":
                raise
    if method in ("auto", "gdb"):
        from pipelab.monitor.gdb_dump import dump_via_gdb

        return dump_via_gdb(pid), "gdb"
    raise DumpError(
        f"No usable method for pid {pid}: dot-dir needs GST_DEBUG_DUMP_DOT_DIR, gdb needs ptrace."
    )
