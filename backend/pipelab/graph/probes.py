"""No-code probe rules: "when <trigger> if <conditions> then <actions>" on pads.

The same ``Action`` vocabulary is used by pipeline API functions
(``graph/dynamic.py``). Semantics are specified in docs/DYNAMIC.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# A JSON primitive. Strings starting with "$" reference a probe variable or a
# builtin ($value, $pad, $pts, $size, $time, $instance, $node, $idle_ms); "$$" escapes "$".
Value = str | int | float | bool | None

TriggerType = Literal["start", "buffer", "event", "idle", "resumed", "interval", "property", "signal"]
ConditionType = Literal[
    "keyframe",
    "flag",
    "size",
    "pts-gap",
    "pts-backwards",
    "every",
    "rate",
    "caps-field",
    "variable",
    "pad",
    "random",
]
ActionType = Literal[
    "pass",
    "drop",
    "block",
    "unblock",
    "remove-probe",
    "post-message",
    "set-property",
    "send-event",
    "request-keyframe",
    "set-variable",
    "increment",
    "log",
    "signal",
    "call",
    "add-instance",
    "remove-instance",
    "restart-instance",
]
Operator = Literal["==", "!=", "<", "<=", ">", ">="]


class Trigger(BaseModel):
    type: TriggerType
    event: str | None = None  # "event": GstEventType nick (eos, caps, segment, tag, flush-start…) or "any"
    ms: int | None = None  # "idle" / "interval"
    property: str | None = None  # "property": the intercepted property name
    name: str | None = None  # "signal": signal name


class Condition(BaseModel):
    type: ConditionType
    negate: bool = False
    flag: str | None = None  # "flag": GstBufferFlags nick (delta-unit, discont, gap, header…)
    op: Operator | None = None
    value: Value = None
    field: str | None = None  # "caps-field"
    name: str | None = None  # "variable": variable name
    n: int | None = None  # "every": every n-th evaluation
    percent: float | None = None  # "random"


class Action(BaseModel):
    type: ActionType
    node: str | None = None  # element *name* (in the current scope)
    pad: Value = None
    property: str | None = None
    value: Value = None
    name: str | None = None  # message / variable / signal name
    fields: dict[str, Value] = Field(default_factory=dict)  # post-message
    message: str | None = None  # log text, "{var}" placeholders are expanded
    level: Literal["info", "warning", "error"] = "info"
    event: str | None = None  # send-event: eos, flush, force-key-unit, custom
    direction: Literal["downstream", "upstream"] = "downstream"
    by: float = 1  # increment
    probe: str | None = None  # signal: target probe id (default: this probe)
    function: str | None = None  # call
    args: dict[str, Value] = Field(default_factory=dict)  # call
    slot: str | None = None  # add/remove/restart-instance
    params: dict[str, Value] = Field(default_factory=dict)  # add-instance
    instance: Value = None  # remove/restart-instance (instance id)


class ProbeRule(BaseModel):
    id: str
    when: Trigger
    conditions: list[Condition] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)


class ProbeTarget(BaseModel):
    kind: Literal["node", "edge"]
    id: str
    pad: str | None = None  # node targets: a pad name/template; None = all sink pads


class ProbeRuleSet(BaseModel):
    id: str
    name: str = "Probe"
    enabled: bool = True
    target: ProbeTarget
    variables: dict[str, Value] = Field(default_factory=dict)
    rules: list[ProbeRule] = Field(default_factory=list)
