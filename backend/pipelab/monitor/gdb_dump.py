"""Force a live, non-cooperative GStreamer process to serialise its pipelines.

We attach with ``gdb`` and, inside the target, call ``gst_debug_bin_to_dot_data`` on every live
top-level ``GstPipeline`` — the same function GStreamer itself uses for ``GST_DEBUG_DUMP_DOT_DIR``.
The process does not need to have been started with any special flag.

Finding the pipeline objects without the application's cooperation is the hard part. GStreamer
keeps no registry of live pipelines, so we find them in the target's heap: every GObject instance
begins with a pointer to its class struct, so we take the ``GstPipeline`` class pointer once and
scan heap memory for aligned words equal to it. Each hit is a ``GstPipeline`` instance; we keep the
top-level ones (no parent) and dump each. Memory is read in bulk inside the gdb Python script and
only the handful of hits are validated by calling into the target, so the scan stays fast.

This is best-effort: it needs permission to ptrace the target, and a pipeline that is an instance of
a *custom subclass* of ``GstPipeline`` has a different class pointer and is not matched (the
``dot-dir`` method covers that). Plain ``gst_pipeline_new`` / ``gst-launch`` pipelines are matched
exactly.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipelab.monitor.dump import DumpError

# Printed by the in-process gdb script around each dumped graph so we can split the output.
_BEGIN = "@@PIPELAB_DOT_BEGIN@@"
_END = "@@PIPELAB_DOT_END@@"

# GObject/GStreamer heap scan, run as a gdb Python script inside the attached process.
_GDB_SCRIPT = r"""
set pagination off
set unwindonsignal on
set unwind-on-terminating-exception on
handle SIGSEGV SIGBUS nostop noprint pass
python
import gdb

BEGIN = "%(begin)s"
END = "%(end)s"
MAX_REGION = 512 * 1024 * 1024   # never read more than this from one mapping
MAX_HITS = 64                    # plenty of candidate instances; bounds pathological scans
PTR = 8

def ev(expr):
    return gdb.parse_and_eval(expr)

def notice(msg):
    gdb.write("@@PIPELAB_NOTE@@ " + msg + "\n")
    gdb.flush()

inferior = gdb.selected_inferior()
try:
    # The class struct shared by every GstPipeline instance; its address is the first word of each
    # instance. g_type_class_peek returns it without taking a reference (the class is live because a
    # pipeline exists).
    class_ptr = int(ev("(unsigned long)g_type_class_peek((unsigned long)gst_pipeline_get_type())"))
except gdb.error as exc:
    notice("gstreamer symbols not callable: %%s" %% exc)
    class_ptr = 0

def regions():
    out = gdb.execute("info proc mappings", to_string=True)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].startswith("0x"):
            try:
                start = int(parts[0], 16); end = int(parts[1], 16)
            except ValueError:
                continue
            name = parts[-1]
            # Heap and anonymous read/write mappings hold GObject instances.
            if name == "[heap]" or len(parts) == 5 or name == "[anon]":
                yield start, end

def plausible_gobject(buf, off):
    # GObject layout: GTypeClass* g_class (8), volatile guint ref_count (4), gpointer qdata (8).
    # A real live instance has a small positive ref count; this filters heap garbage that merely
    # happens to contain the class pointer, before we risk calling into the target.
    try:
        ref_count = int.from_bytes(buf[off + PTR : off + PTR + 4], "little")
    except (IndexError, ValueError):
        return False
    return 0 < ref_count < 1_000_000

def no_parent(addr):
    try:
        return int(ev("(unsigned long)gst_object_get_parent((void*)%%d)" %% addr)) == 0
    except gdb.error:
        return False

found = []
if class_ptr:
    pattern = class_ptr.to_bytes(PTR, "little")
    for start, end in regions():
        size = min(end - start, MAX_REGION)
        try:
            buf = inferior.read_memory(start, size).tobytes()
        except (gdb.error, gdb.MemoryError):
            continue
        idx = buf.find(pattern)
        while idx != -1 and len(found) < MAX_HITS:
            addr = start + idx
            if idx %% PTR == 0 and addr not in found and plausible_gobject(buf, idx) and no_parent(addr):
                found.append(addr)
            idx = buf.find(pattern, idx + 1)
        if len(found) >= MAX_HITS:
            break

notice("class_ptr=0x%%x pipelines found: %%d" %% (class_ptr, len(found)))
for addr in found:
    try:
        data = ev("(char*)gst_debug_bin_to_dot_data((void*)%%d, 15)" %% addr)
        text = data.string()
        gdb.write(BEGIN + "\n")
        gdb.write(text)
        gdb.write("\n" + END + "\n")
        gdb.flush()
        ev("(void)g_free((void*)%%d)" %% int(data))
    except gdb.error as exc:
        notice("dump failed for 0x%%x: %%s" %% (addr, exc))
end
"""


def _render_script() -> str:
    return _GDB_SCRIPT % {"begin": _BEGIN, "end": _END}


def dump_via_gdb(pid: int, timeout: float = 60.0) -> str:
    """Attach to ``pid`` and return the ``.dot`` of its first live pipeline.

    Raises :class:`DumpError` if gdb is unavailable, the attach fails, or no pipeline is found.
    """
    gdb_bin = shutil.which("gdb")
    if not gdb_bin:
        raise DumpError("gdb is not installed in this image; cannot use the gdb method.")

    with tempfile.NamedTemporaryFile("w", suffix=".gdb", delete=False) as handle:
        handle.write(_render_script())
        script_path = handle.name
    try:
        proc = subprocess.run(
            [gdb_bin, "-batch", "-nx", "-p", str(pid), "-x", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise DumpError(f"gdb timed out after {timeout}s attaching to pid {pid}.") from exc
    finally:
        Path(script_path).unlink(missing_ok=True)

    output = proc.stdout + "\n" + proc.stderr
    dots = _extract(proc.stdout)
    if not dots:
        reason = _failure_reason(output)
        raise DumpError(f"gdb could not dump a pipeline from pid {pid}: {reason}")
    # Return the largest graph (the most complete pipeline).
    return max(dots, key=len)


def _extract(stdout: str) -> list[str]:
    graphs: list[str] = []
    while _BEGIN in stdout and _END in stdout:
        _, _, rest = stdout.partition(_BEGIN)
        body, _, stdout = rest.partition(_END)
        graphs.append(body.strip())
    return graphs


def _failure_reason(output: str) -> str:
    notes = [
        ln.split("@@PIPELAB_NOTE@@", 1)[1].strip() for ln in output.splitlines() if "@@PIPELAB_NOTE@@" in ln
    ]
    if any("ptrace" in ln.lower() or "permission" in ln.lower() for ln in output.splitlines()):
        return "permission denied (need CAP_SYS_PTRACE / same user and PID namespace)."
    if notes:
        return "; ".join(notes[-3:])
    return "no live top-level pipeline located on the heap."
