"""Setting element and pad properties the way gst-launch does."""

from __future__ import annotations

from pipelab.gst import Gst
from pipelab.gst.values import to_launch_string


def is_pad_property(target: Gst.Object, name: str) -> bool:
    pspec = target.find_property(name)
    return pspec is not None and pspec.value_type.is_a(Gst.Pad.__gtype__)


def apply_property(target: Gst.Object, name: str, value: str | int | float | bool) -> str | None:
    """Set a property from its graph value; returns an error message.

    ``target`` is an element or a pad. GstPad-typed element properties take
    the name of one of the element's pads.
    """
    pspec = target.find_property(name)
    if pspec is None:
        return f"no property '{name}'"
    if isinstance(target, Gst.Element) and is_pad_property(target, name):
        pad = target.get_static_pad(str(value))
        if pad is None:
            return f"'{name}': pad '{value}' does not exist"
        target.set_property(name, pad)
        return None
    Gst.util_set_object_arg(target, name, to_launch_string(value))
    return None
