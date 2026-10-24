"""Description of the probe rule vocabulary for form-based editors (the "cartilla")."""

from __future__ import annotations

from typing import Any

from pipelab.gst import Gst


def _field(name: str, kind: str, label: str, required: bool = True, options: list[str] | None = None) -> dict:
    spec: dict[str, Any] = {"name": name, "kind": kind, "label": label, "required": required}
    if options:
        spec["options"] = options
    return spec


def _spec(type_: str, label: str, description: str, *fields: dict) -> dict:
    return {"type": type_, "label": label, "description": description, "fields": list(fields)}


TRIGGERS = [
    _spec("start", "Pipeline starts", "Once, when the pipeline first reaches PLAYING."),
    _spec("buffer", "A buffer passes", "Every buffer crossing the watched pads."),
    _spec(
        "event",
        "An event passes",
        "Every downstream event of the chosen type.",
        _field("event", "event", "Event"),
    ),
    _spec(
        "idle",
        "No data for…",
        "Once, when no buffer crossed the pads for the given time (watchdog). Re-armed by the next buffer.",
        _field("ms", "ms", "Timeout (ms)"),
    ),
    _spec("resumed", "Data flows again", "First buffer after an idle trigger fired."),
    _spec("interval", "Every…", "Periodically while running.", _field("ms", "ms", "Period (ms)")),
    _spec(
        "property",
        "Property change requested",
        "A live change of the property was requested on the "
        "element; the rule intercepts it unless it executes Pass.",
        _field("property", "property", "Property"),
    ),
    _spec(
        "signal",
        "Signal received",
        "Raised from the UI, a pipeline function or another probe.",
        _field("name", "string", "Signal name"),
    ),
]

CONDITIONS = [
    _spec("keyframe", "Is a keyframe", "The buffer has no delta-unit flag."),
    _spec("flag", "Buffer has flag", "A buffer flag is set.", _field("flag", "flag", "Flag")),
    _spec(
        "size", "Buffer size", "Size in bytes.", _field("op", "op", "Op"), _field("value", "value", "Bytes")
    ),
    _spec(
        "pts-gap",
        "PTS gap",
        "Milliseconds between consecutive timestamps.",
        _field("op", "op", "Op"),
        _field("value", "value", "ms"),
    ),
    _spec("pts-backwards", "PTS goes backwards", "The timestamp is older than the previous one."),
    _spec("every", "Every n-th time", "True once every n evaluations of this rule.", _field("n", "int", "n")),
    _spec(
        "rate",
        "Buffer rate",
        "Buffers per second over the last second.",
        _field("op", "op", "Op"),
        _field("value", "value", "Buffers/s"),
    ),
    _spec(
        "caps-field",
        "Caps field",
        "A field of the pad's current caps.",
        _field("field", "string", "Field"),
        _field("op", "op", "Op"),
        _field("value", "value", "Value"),
    ),
    _spec(
        "variable",
        "Variable",
        "Compare a probe variable.",
        _field("name", "string", "Variable"),
        _field("op", "op", "Op"),
        _field("value", "value", "Value"),
    ),
    _spec(
        "pad",
        "Pad",
        "Name of the pad the data crosses.",
        _field("op", "op", "Op"),
        _field("value", "value", "Pad name"),
    ),
    _spec("random", "Random", "True with the given probability.", _field("percent", "percent", "Percent")),
]

ACTIONS = [
    _spec("pass", "Pass", "Let the buffer/event through (or apply an intercepted property)."),
    _spec("drop", "Drop", "Drop the buffer/event."),
    _spec("block", "Block the pad", "Hold the data flow until Unblock."),
    _spec("unblock", "Unblock the pad", "Release a blocked pad."),
    _spec("remove-probe", "Remove this probe", "Disable the whole rule set."),
    _spec(
        "post-message",
        "Post bus message",
        "Application message on the bus; the owning software receives it.",
        _field("name", "string", "Message name"),
        _field("fields", "fields", "Fields", required=False),
    ),
    _spec(
        "set-property",
        "Set property",
        "Change a property of an element (pad names for GstPad properties).",
        _field("node", "node", "Element"),
        _field("property", "property", "Property"),
        _field("value", "value", "Value"),
        _field("pad", "pad", "Pad", required=False),
    ),
    _spec(
        "send-event",
        "Send event",
        "Push an event on the watched pad (or the given pad).",
        _field("event", "string", "Event", options=["eos", "flush", "force-key-unit", "custom"]),
        _field("direction", "direction", "Direction"),
        _field("pad", "pad", "Pad", required=False),
        _field("name", "string", "Custom event name", required=False),
        _field("fields", "fields", "Custom event fields", required=False),
    ),
    _spec(
        "request-keyframe",
        "Request keyframe",
        "Ask the encoder upstream for a key unit.",
        _field("pad", "pad", "Pad", required=False),
    ),
    _spec(
        "set-variable",
        "Set variable",
        "Store a value in a probe variable.",
        _field("name", "string", "Variable"),
        _field("value", "value", "Value"),
    ),
    _spec(
        "increment",
        "Increment variable",
        "Add to a numeric variable.",
        _field("name", "string", "Variable"),
        _field("by", "float", "By", required=False),
    ),
    _spec(
        "log",
        "Log",
        "Message in the Probe tab; {name} expands variables and builtins.",
        _field("message", "string", "Message"),
        _field("level", "level", "Level", required=False),
    ),
    _spec(
        "signal",
        "Send signal",
        "Fire the signal rules of a probe (this one by default).",
        _field("name", "string", "Signal"),
        _field("probe", "probe", "Probe", required=False),
        _field("value", "value", "Value", required=False),
    ),
    _spec(
        "call",
        "Call function",
        "Call a pipeline API function.",
        _field("function", "function", "Function"),
        _field("args", "args", "Arguments", required=False),
    ),
    _spec(
        "add-instance",
        "Add instance",
        "Add an instance to a slot.",
        _field("slot", "slot", "Slot"),
        _field("params", "params", "Parameters", required=False),
    ),
    _spec(
        "remove-instance",
        "Remove instance",
        "Remove an instance from a slot.",
        _field("slot", "slot", "Slot"),
        _field("instance", "instance", "Instance id"),
    ),
    _spec(
        "restart-instance",
        "Restart instance",
        "Rebuild an instance with the same parameters.",
        _field("slot", "slot", "Slot"),
        _field("instance", "instance", "Instance id"),
    ),
]

BUILTINS = [
    {"name": "$value", "description": "Value of the trigger (requested property value, signal value)."},
    {"name": "$pad", "description": "Name of the pad the data crosses."},
    {"name": "$pts", "description": "Buffer PTS in seconds."},
    {"name": "$size", "description": "Buffer size in bytes."},
    {"name": "$time", "description": "Seconds since the pipeline started."},
    {"name": "$instance", "description": "Component instance name (inside a component), else empty."},
    {"name": "$node", "description": "Name of the target element."},
    {"name": "$idle_ms", "description": "Milliseconds without data (idle trigger)."},
]

EVENTS = [
    "any",
    "eos",
    "caps",
    "segment",
    "tag",
    "stream-start",
    "flush-start",
    "flush-stop",
    "gap",
    "segment-done",
    "custom-downstream",
    "custom-downstream-oob",
    "protection",
    "instant-rate-change",
]
OPERATORS = ["==", "!=", "<", "<=", ">", ">="]


def buffer_flags() -> list[str]:
    values = Gst.BufferFlags.__flags_values__.values()
    return sorted({nick for value in values for nick in (value.value_nicks or [])})


def probe_schema() -> dict[str, Any]:
    return {
        "triggers": TRIGGERS,
        "conditions": CONDITIONS,
        "actions": ACTIONS,
        "builtins": BUILTINS,
        "events": EVENTS,
        "flags": buffer_flags(),
        "operators": OPERATORS,
    }
