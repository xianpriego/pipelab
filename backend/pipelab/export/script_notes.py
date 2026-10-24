"""Probe scripts as porting notes for the C, Rust and shell exports."""

from __future__ import annotations

from pipelab.export.python_scripts import enabled_scripts
from pipelab.graph.models import Graph

_HOWTO = {
    "c": "gst_pad_add_probe (pad, GST_PAD_PROBE_TYPE_BUFFER, cb, NULL, NULL); a keyframe is "
    "!GST_BUFFER_FLAG_IS_SET (buf, GST_BUFFER_FLAG_DELTA_UNIT); return GST_PAD_PROBE_DROP to drop.",
    "rust": "pad.add_probe(gst::PadProbeType::BUFFER, |pad, info| ...); a keyframe is "
    "!buffer.flags().contains(gst::BufferFlags::DELTA_UNIT); return gst::PadProbeReturn::Drop to drop.",
    "shell": "gst-launch-1.0 cannot run probes: use the Python export, which embeds them.",
}


def script_notes(graph: Graph, language: str) -> list[str]:
    """Plain text lines (to be commented by the caller); empty without scripts."""
    scripts = enabled_scripts(graph)
    if not scripts:
        return []
    lines = ["Probe scripts designed in Pipelab (the Python export runs them as-is).", _HOWTO[language], ""]
    for script, (kind, element, pad) in scripts:
        where = f"element {element}" if kind == "element" else f"the link leaving {element}.{pad}"
        lines.append(f"--- {script.name} on {where}")
        lines += script.code.rstrip("\n").splitlines()
        lines.append("")
    return lines


def comment_block(lines: list[str], style: str) -> str:
    if not lines:
        return ""
    if style == "c":
        body = "\n".join(f" * {line}".rstrip() for line in lines)
        return "\n/*\n" + body.replace("*/", "* /") + "\n */\n"
    prefix = "//" if style == "rust" else "#"
    return "\n" + "\n".join(f"{prefix} {line}".rstrip() for line in lines) + "\n"
