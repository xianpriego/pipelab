"""Conversion of GObject property values to JSON friendly primitives.

Values are rendered with the same textual conventions ``gst-launch-1.0``
accepts, so they can be fed back through ``Gst.util_set_object_arg``.
"""

from __future__ import annotations

import math
from typing import Any

from pipelab.gst import GObject, Gst

JsonValue = str | int | float | bool | None


def flags_to_string(value: Any) -> str:
    nicks = list(getattr(value, "value_nicks", []) or [])
    return "+".join(nicks) if nicks else str(int(value))


def enum_to_string(value: Any) -> str | int:
    nick = getattr(value, "value_nick", None)
    return nick if nick else int(value)


def to_json_value(value: Any) -> JsonValue:
    """Best effort conversion of a Python/GObject value to a JSON primitive."""
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, GObject.GFlags):
        return flags_to_string(value)
    if isinstance(value, GObject.GEnum):
        return enum_to_string(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Gst.Caps | Gst.Structure):
        return value.to_string()
    if isinstance(value, Gst.Fraction):
        return f"{value.num}/{value.denom}"
    if isinstance(value, Gst.Object):
        return value.get_name()
    return _serialize_with_gst(value)


def _serialize_with_gst(value: Any) -> JsonValue:
    try:
        serialized = Gst.value_serialize(value)
    except (TypeError, ValueError):
        return None
    return serialized if isinstance(serialized, str) else None


def to_launch_string(value: str | int | float | bool) -> str:
    """Render a stored property value as the string gst-launch would parse."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return repr(value)
    return str(value)
