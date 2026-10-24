"""Conversion of bus messages into JSON runtime events."""

from __future__ import annotations

import time
from typing import Any

from pipelab.gst import Gst
from pipelab.gst.values import to_json_value
from pipelab.runtime.worker.hints import hint_for

_KINDS = {
    Gst.MessageType.ERROR: "error",
    Gst.MessageType.WARNING: "warning",
    Gst.MessageType.INFO: "info",
    Gst.MessageType.EOS: "eos",
    Gst.MessageType.STATE_CHANGED: "state-changed",
    Gst.MessageType.QOS: "qos",
    Gst.MessageType.ELEMENT: "element",
    Gst.MessageType.TAG: "tag",
    Gst.MessageType.LATENCY: "latency",
    Gst.MessageType.STREAM_START: "stream-start",
    Gst.MessageType.BUFFERING: "buffering",
    Gst.MessageType.CLOCK_LOST: "clock-lost",
    Gst.MessageType.APPLICATION: "application",
}
# Messages too frequent or internal to be worth showing. Compared by equality:
# "extended" message types (EXTENDED + n) are not independent bit flags.
IGNORED = {
    Gst.MessageType.ASYNC_DONE,
    Gst.MessageType.NEW_CLOCK,
    Gst.MessageType.STREAM_STATUS,
    Gst.MessageType.DURATION_CHANGED,
    Gst.MessageType.NEED_CONTEXT,
    Gst.MessageType.HAVE_CONTEXT,
    Gst.MessageType.RESET_TIME,
    Gst.MessageType.STREAM_COLLECTION,
    Gst.MessageType.STREAMS_SELECTED,
    Gst.MessageType.PROPERTY_NOTIFY,
}


def _value(value: Any) -> Any:
    if isinstance(value, list | tuple):
        return [_value(v) for v in value]
    return to_json_value(value)


def structure_fields(structure: Gst.Structure | None) -> dict[str, Any]:
    if structure is None:
        return {}
    fields: dict[str, Any] = {}
    for index in range(structure.n_fields()):
        name = structure.nth_field_name(index)
        try:
            fields[name] = _value(structure.get_value(name))
        except TypeError:
            fields[name] = None
    return fields


def message_event(
    message: Gst.Message, element_ids: dict[Gst.Element, str], started: float
) -> dict[str, Any]:
    source, node_id = source_node(message.src, element_ids)
    event: dict[str, Any] = {
        "type": "bus",
        "kind": _KINDS.get(message.type, "other"),
        "source": source,
        "node_id": node_id,
        "path": message.src.get_path_string() if isinstance(message.src, Gst.Object) else None,
        "time": round(time.monotonic() - started, 3),
        "text": "",
    }
    if message.type in (Gst.MessageType.ERROR, Gst.MessageType.WARNING, Gst.MessageType.INFO):
        parse = {
            Gst.MessageType.ERROR: message.parse_error,
            Gst.MessageType.WARNING: message.parse_warning,
            Gst.MessageType.INFO: message.parse_info,
        }[message.type]
        error, debug = parse()
        event.update(text=error.message, debug=debug, hint=hint_for(error, debug))
    elif message.type == Gst.MessageType.STATE_CHANGED:
        old, new, _pending = message.parse_state_changed()
        event["text"] = f"{old.value_nick} → {new.value_nick}"
    elif message.type == Gst.MessageType.TAG:
        event["text"] = message.parse_tag().to_string()
    elif message.type == Gst.MessageType.BUFFERING:
        event["text"] = f"buffering {message.parse_buffering()}%"
    else:
        structure = message.get_structure()
        event["text"] = structure.get_name() if structure is not None else message.type.first_value_nick
        event["fields"] = structure_fields(structure)
        if message.type == Gst.MessageType.APPLICATION and structure is not None:
            event["name"] = structure.get_name()
    return event


def source_node(source: Any, element_ids: dict[Gst.Element, str]) -> tuple[str | None, str | None]:
    """Name and global node id of the innermost graph element a message comes from."""
    obj = source
    while obj is not None:
        if isinstance(obj, Gst.Element) and obj in element_ids:
            return obj.get_name(), element_ids[obj]
        obj = obj.get_parent() if isinstance(obj, Gst.Object) else None
    name = source.get_name() if isinstance(source, Gst.Object) else None
    return name, None
