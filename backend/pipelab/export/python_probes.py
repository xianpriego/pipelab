"""Probe rule sets as explicit Python classes (one branch per rule)."""

from __future__ import annotations

from pipelab.export.common import camel_case
from pipelab.graph.probes import Action, Condition, ProbeRule, ProbeRuleSet

BUILTINS = ("value", "pad", "pts", "size", "time", "instance", "node", "idle_ms")
_METHODS = {
    "start": ("on_start", "ctx"),
    "buffer": ("on_buffer", "ctx"),
    "event": ("on_event", "ctx, event"),
    "idle": ("on_idle", "ctx, index"),
    "resumed": ("on_resumed", "ctx"),
    "interval": ("on_interval", "ctx, index"),
    "property": ("on_property", "ctx, prop"),
    "signal": ("on_signal", "ctx, name"),
}
_VERDICT_METHODS = {"on_buffer", "on_event"}


def literal(value: object) -> str:
    return repr(value)


class ValueRenderer:
    """Python expression for a rule ``Value`` ("$name" references)."""

    def __init__(self, variables: set[str], params: set[str] | None = None, scope: str = "probe") -> None:
        self.variables, self.params, self.scope = variables, params or set(), scope

    def __call__(self, value: object) -> str:
        if isinstance(value, str) and value.startswith("$$"):
            return literal(value[1:])
        if isinstance(value, str) and value.startswith("$"):
            name = value[1:]
            if self.scope == "function":
                return name if name in self.params else ("self._elapsed()" if name == "time" else "None")
            if name in self.variables:
                return f"self.vars[{name!r}]"
            if name in BUILTINS:
                return f"self.builtin({name!r}, ctx)"
            return "None"
        return literal(value)

    def mapping(self, values: dict) -> str:
        return "{" + ", ".join(f"{k!r}: {self(v)}" for k, v in values.items()) + "}"


def condition_expr(condition: Condition, rule: ProbeRule, value) -> str:
    op = condition.op or "=="
    v = value(condition.value)
    expressions = {
        "keyframe": "self.is_keyframe(ctx)",
        "flag": f"self.has_flag(ctx, {condition.flag or 'delta-unit'!r})",
        "size": f"compare(ctx.size, {op!r}, {v})",
        "pts-gap": f"self.gap_ms is not None and compare(self.gap_ms, {op!r}, {v})",
        "pts-backwards": "self.backwards",
        "every": f"self.every({rule.id!r}, {condition.n or 1})",
        "rate": f"compare(self.rate(), {op!r}, {v})",
        "caps-field": f"compare(self.caps_field(ctx, {condition.field or ''!r}), {op!r}, {v})",
        "variable": f"compare(self.vars.get({condition.name or ''!r}), {op!r}, {v})",
        "pad": f"compare(ctx.pad_name, {op!r}, {v})",
        "random": f"self.chance({condition.percent or 0})",
    }
    expression = expressions[condition.type]
    return f"not ({expression})" if condition.negate else expression


class ProbeActions:
    """Statements for probe rule actions."""

    def __init__(self, value: ValueRenderer, slots: dict[str, str], functions: dict[str, str]) -> None:
        self.value, self.slots, self.functions = value, slots, functions

    def statements(self, action: Action, method: str) -> list[str]:
        v = self.value
        kind = action.type
        if kind in ("pass", "drop"):
            if method == "on_property":
                return ["handled = False"] if kind == "pass" else ["handled = True"]
            return (
                [f"verdict = {kind.upper()}"] if method in _VERDICT_METHODS else [f"# {kind}: no data here"]
            )
        simple = {
            "block": "self.block()",
            "unblock": "self.unblock()",
            "remove-probe": "self.remove()",
            "post-message": f"self.post({action.name or 'message'!r}, {v.mapping(action.fields)})",
            "set-property": f"self.set_property({action.node or ''!r}, {action.property or ''!r}, "
            f"{v(action.value)}, {v(action.pad)})",
            "send-event": f"self.send({action.event or 'eos'!r}, {action.direction == 'downstream'}, ctx, "
            f"{v(action.pad)}, {action.name!r}, {v.mapping(action.fields)})",
            "request-keyframe": f"self.request_keyframe(ctx, {v(action.pad)})",
            "set-variable": f"self.vars[{action.name or ''!r}] = {v(action.value)}",
            "increment": f"self.vars[{action.name or ''!r}] = (self.vars.get({action.name or ''!r}) or 0) + "
            f"{action.by!r}",
            "log": f"self.log({action.message or ''!r}, {action.level!r}, ctx)",
        }
        if kind in simple:
            return [simple[kind]]
        if kind == "signal":
            target = f"self.sibling({action.probe!r})" if action.probe else "self.probe_id"
            return [f"self.host.defer('signal', {target}, {action.name or ''!r}, {v(action.value)})"]
        if kind == "call":
            function = self.functions.get(action.function or "", action.function or "")
            return [f"self.host.defer('call', {function!r}, {v.mapping(action.args)})"]
        slot = self.slots.get(action.slot or "", action.slot or "")
        if kind == "add-instance":
            return [f"self.host.defer('add', {slot!r}, {v.mapping(action.params)})"]
        operation = "remove" if kind == "remove-instance" else "restart"
        return [f"self.host.defer({operation!r}, {slot!r}, {v(action.instance)})"]


def _guard(rule: ProbeRule) -> str | None:
    when = rule.when
    if when.type == "event" and when.event not in (None, "any"):
        return f"event == {when.event!r}"
    if when.type == "property":
        return f"prop == {when.property or ''!r}"
    if when.type == "signal" and when.name:
        return f"name == {when.name!r}"
    return None


def _rule_block(rule: ProbeRule, index: int | None, method: str, actions: ProbeActions) -> list[str]:
    parts = []
    if index is not None:
        parts.append(f"index == {index}")
    guard = _guard(rule)
    if guard:
        parts.append(guard)
    parts += [condition_expr(c, rule, actions.value) for c in rule.conditions]
    body = ["handled = True"] if method == "on_property" else []
    for action in rule.actions:
        body += actions.statements(action, method)
    lines = [f"        # {rule.id}: when {rule.when.type}"]
    if parts:
        condition = " and ".join(parts)
        if len(condition) > 80 and len(parts) > 1:  # one condition per line, like ruff format
            lines += [
                "        if (",
                f"            {parts[0]}",
                *[f"            and {p}" for p in parts[1:]],
                "        ):",
            ]
        else:
            lines.append(f"        if {condition}:")
        lines += [f"            {line}" for line in body or ["pass"]]
    else:
        lines += [f"        {line}" for line in body or ["pass"]]
    return lines


def class_name(rule_set: ProbeRuleSet, owner: str) -> str:
    return camel_case(f"{owner} {rule_set.name} {rule_set.id}") + "Probe"


def render_rule_set(
    rule_set: ProbeRuleSet, cls: str, slots: dict[str, str], functions: dict[str, str]
) -> list[str]:
    value = ValueRenderer(set(rule_set.variables))
    actions = ProbeActions(value, slots, functions)
    idle = [r for r in rule_set.rules if r.when.type == "idle"]
    intervals = [r for r in rule_set.rules if r.when.type == "interval"]
    lines = [
        "",
        "",
        f"class {cls}(RuleSet):",
        f'    """Probe rule set {rule_set.name!r} on {rule_set.target.kind} {rule_set.target.id}."""',
        "",
        f"    NAME = {rule_set.name!r}",
        f"    IDLE = {tuple(r.when.ms or 1000 for r in idle)!r}",
        f"    INTERVALS = {tuple(r.when.ms or 1000 for r in intervals)!r}",
        f"    VARIABLES = {rule_set.variables!r}",
    ]
    for trigger, (method, args) in _METHODS.items():
        rules = [r for r in rule_set.rules if r.when.type == trigger]
        if not rules:
            continue
        ordered = idle if trigger == "idle" else intervals if trigger == "interval" else rules
        lines += ["", f"    def {method}(self, {args}):"]
        if method in _VERDICT_METHODS:
            lines.append("        verdict = PASS")
        if method == "on_property":
            lines.append("        handled = False")
        for rule in rules:
            index = ordered.index(rule) if trigger in ("idle", "interval") else None
            lines += _rule_block(rule, index, method, actions)
        if method in _VERDICT_METHODS:
            lines.append("        return verdict")
        elif method == "on_property":
            lines.append("        return handled")
    return lines
