"""Live inspection and modification of a running element."""

from __future__ import annotations

from typing import Any

from pipelab.gst import GObject, Gst
from pipelab.gst.values import to_json_value
from pipelab.runtime.worker.builder import apply_property, is_pad_property

_HIDDEN = {"name", "parent"}


def _readable(obj: Gst.Object) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for pspec in obj.list_properties():
        if pspec.name in _HIDDEN or not pspec.flags & GObject.ParamFlags.READABLE:
            continue
        try:
            values[pspec.name] = to_json_value(obj.get_property(pspec.name))
        except Exception:  # noqa: BLE001 - some getters fail in some states
            values[pspec.name] = None
    return values


def read_properties(element: Gst.Element) -> dict[str, Any]:
    pads = {
        pad.get_name(): _readable(pad)
        for pad in element.pads
        if type(pad) is not Gst.Pad and pad.list_properties()
    }
    return {"properties": _readable(element), "pads": {k: v for k, v in pads.items() if v}}


def set_live_property(element: Gst.Element, name: str, value: Any, pad_name: str | None) -> dict[str, Any]:
    """Apply a property while running and report the value actually in effect."""
    target: Gst.Object = element
    if pad_name:
        pad = element.get_static_pad(pad_name)
        if pad is None:
            return {"ok": False, "error": f"pad '{pad_name}' does not exist"}
        target = pad
    error = apply_property(target, name, value)
    if error:
        return {"ok": False, "error": error}
    if is_pad_property(target, name):
        # Selectors switch on their next buffer; the "property" event with origin
        # "runtime" confirms it, an immediate read would still show the old pad.
        return {"ok": True, "value": str(value)}
    pspec = target.find_property(name)
    if pspec is not None and pspec.flags & GObject.ParamFlags.READABLE:
        return {"ok": True, "value": to_json_value(target.get_property(name))}
    return {"ok": True, "value": value}


def dot_graph(pipeline: Gst.Pipeline) -> str:
    return Gst.debug_bin_to_dot_data(pipeline, Gst.DebugGraphDetails.ALL)
