"""Probe rule sets as explicit Rust types (one ``if`` per rule) implementing ``rt::Rules``."""

from __future__ import annotations

from pipelab.export.common import camel_case
from pipelab.export.rust_syntax import rust_float, rust_str, uses_name, value_literal
from pipelab.graph.probes import Action, Condition, ProbeRule, ProbeRuleSet

BUILTINS = ("value", "pad", "pts", "size", "time", "instance", "node", "idle_ms")

# trigger → (method, extra parameters, return type)
_METHODS = {
    "start": ("on_start", [], None),
    "buffer": ("on_buffer", [], "Verdict"),
    "event": ("on_event", [("event", "&str")], "Verdict"),
    "idle": ("on_idle", [("index", "usize")], None),
    "resumed": ("on_resumed", [], None),
    "interval": ("on_interval", [("index", "usize")], None),
    "property": ("on_property", [("property", "&str")], "bool"),
    "signal": ("on_signal", [("name", "&str")], None),
}
_DEFERRED = {"signal", "call", "add-instance", "remove-instance", "restart-instance"}


class RustValues:
    """Rust expression for a rule ``Value`` ("$name" references)."""

    def __init__(self, variables: set[str], params: set[str] | None = None, scope: str = "probe") -> None:
        self.variables, self.params, self.scope = variables, params or set(), scope

    def __call__(self, value: object) -> str:
        if isinstance(value, str) and value.startswith("$$"):
            return value_literal(value[1:])
        if isinstance(value, str) and value.startswith("$"):
            name = value[1:]
            if self.scope == "function":
                if name in self.params:
                    return f"Value::from({name})"
                return "Value::Float(self.elapsed())" if name == "time" else "Value::Null"
            if name in self.variables:
                return f"self.vars.get({rust_str(name)})"
            if name in BUILTINS:
                return f"core.builtin({rust_str(name)}, ctx)"
            return "Value::Null"
        return value_literal(value)

    def fields(self, values: dict) -> str:
        """``Vec<(&str, Value)>`` (message and event fields)."""
        if not values:
            return "Vec::new()"
        return "vec![" + ", ".join(f"({rust_str(k)}, {self(v)})" for k, v in values.items()) + "]"

    def args(self, values: dict) -> str:
        """``Vec<(String, Value)>`` (function arguments, instance parameters)."""
        return f"rt::args({self.fields(values)})"


def _compare(left: str, condition: Condition, value: RustValues) -> str:
    return f"rt::compare(&{left}, {rust_str(condition.op or '==')}, &{value(condition.value)})"


def condition_expr(condition: Condition, rule: ProbeRule, value: RustValues) -> str:
    kind = condition.type
    if kind == "keyframe":
        expression = "core.is_keyframe(ctx)"
    elif kind == "flag":
        expression = f"core.has_flag(ctx, {rust_str(condition.flag or 'delta-unit')})"
    elif kind == "size":
        expression = _compare('core.builtin("size", ctx)', condition, value)
    elif kind == "pts-gap":
        expression = f"core.gap_ms().is_some_and(|gap| {_compare('Value::Float(gap)', condition, value)})"
    elif kind == "pts-backwards":
        expression = "core.backwards()"
    elif kind == "every":
        expression = f"core.every({rust_str(rule.id)}, {max(condition.n or 1, 1)})"
    elif kind == "rate":
        expression = _compare("core.rate()", condition, value)
    elif kind == "caps-field":
        expression = _compare(f"core.caps_field(ctx, {rust_str(condition.field or '')})", condition, value)
    elif kind == "variable":
        expression = _compare(f"self.vars.get({rust_str(condition.name or '')})", condition, value)
    elif kind == "pad":
        expression = _compare('core.builtin("pad", ctx)', condition, value)
    else:  # random
        expression = f"core.chance({rust_float(condition.percent or 0)})"
    return f"!({expression})" if condition.negate else expression


class RustActions:
    """Statements for probe rule actions (verdicts are handled by ``_rule_block``)."""

    def __init__(self, value: RustValues, slots: dict[str, str], functions: dict[str, str]) -> None:
        self.value, self.slots, self.functions = value, slots, functions

    def statement(self, action: Action) -> str | None:
        v = self.value
        kind = action.type
        if kind in ("pass", "drop"):
            return None
        if kind in _DEFERRED:
            return f"core.defer({self._deferred(action)});"
        simple = {
            "block": "core.block();",
            "unblock": "core.unblock();",
            "remove-probe": "core.remove();",
            "post-message": f"core.post({rust_str(action.name or 'message')}, {v.fields(action.fields)});",
            "set-property": "core.set_property("
            f"{rust_str(action.node or '')}, {rust_str(action.property or '')}, "
            f"&{v(action.value)}, &{v(action.pad)});",
            "send-event": "core.send("
            f"{rust_str(action.event or 'eos')}, {_bool(action.direction == 'downstream')}, "
            f"ctx, &{v(action.pad)}, {_option(action.name)}, {v.fields(action.fields)});",
            "request-keyframe": f"core.request_keyframe(ctx, &{v(action.pad)});",
            "set-variable": f"self.vars.set({rust_str(action.name or '')}, {v(action.value)});",
            "increment": f"self.vars.increment({rust_str(action.name or '')}, {rust_float(action.by)});",
            "log": f"core.log(Self::NAME, {rust_str(action.message or '')}, {rust_str(action.level)}, ctx, "
            "&self.vars);",
        }
        return simple[kind]

    def _deferred(self, action: Action) -> str:
        v = self.value
        if action.type == "signal":
            target = f"core.sibling({rust_str(action.probe)})" if action.probe else "core.probe_id.clone()"
            return f"rt::Deferred::Signal({target}, {rust_str(action.name or '')}.into(), {v(action.value)})"
        if action.type == "call":
            function = self.functions.get(action.function or "", action.function or "")
            return f"rt::Deferred::Call({rust_str(function)}.into(), {v.args(action.args)})"
        slot = rust_str(self.slots.get(action.slot or "", action.slot or ""))
        if action.type == "add-instance":
            return f"rt::Deferred::Add({slot}.into(), {v.args(action.params)})"
        operation = "Remove" if action.type == "remove-instance" else "Restart"
        return f"rt::Deferred::{operation}({slot}.into(), {v(action.instance)})"


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _option(text: str | None) -> str:
    return f"Some({rust_str(text)})" if text else "None"


def _guard(rule: ProbeRule) -> str | None:
    when = rule.when
    if when.type == "event" and when.event not in (None, "any"):
        return f"event == {rust_str(when.event)}"
    if when.type == "property" and when.property:
        return f"property == {rust_str(when.property)}"
    if when.type == "signal" and when.name:
        return f"name == {rust_str(when.name)}"
    return None


def _outcome(rule: ProbeRule, returns: str | None) -> str | None:
    """The verdict statement of a rule (the last pass/drop wins)."""
    verdicts = [a.type for a in rule.actions if a.type in ("pass", "drop")]
    if returns == "bool":  # property: intercepted unless the rule passes
        return f"handled = {_bool(not verdicts or verdicts[-1] == 'drop')};"
    if returns == "Verdict" and verdicts:
        return f"verdict = Verdict::{verdicts[-1].capitalize()};"
    return None


def _rule_block(
    rule: ProbeRule, index: int | None, returns: str | None, actions: RustActions
) -> tuple[list[str], bool]:
    """Lines of one rule and whether it runs unconditionally."""
    parts = [f"index == {index}"] if index is not None else []
    guard = _guard(rule)
    if guard:
        parts.append(guard)
    parts += [condition_expr(c, rule, actions.value) for c in rule.conditions]
    body = [s for s in (actions.statement(a) for a in rule.actions) if s]
    if returns is None and any(a.type in ("pass", "drop") for a in rule.actions):
        body.append("// pass / drop: no buffer or event to decide on here")
    outcome = _outcome(rule, returns)
    if outcome:
        body.append(outcome)
    lines = [f"// {rule.id}: when {rule.when.type}"]
    if parts:
        condition = " && ".join(parts)
        if len(condition) > 80 and len(parts) > 1:  # one condition per line, like rustfmt
            lines += [f"if {parts[0]}", *[f"    && {part}" for part in parts[1:]], "{"]
        else:
            lines.append(f"if {condition} {{")
        lines += [f"    {line}" for line in body]
        lines.append("}")
    else:
        lines += body
    return lines, not parts and outcome is not None


def type_name(rule_set: ProbeRuleSet, owner: str) -> str:
    return camel_case(f"{owner} {rule_set.name} {rule_set.id}") + "Rules"


def _method(
    trigger: str, rules: list[ProbeRule], ordered: list[ProbeRule], actions: RustActions
) -> list[str]:
    method, extra, returns = _METHODS[trigger]
    body: list[str] = []
    unconditional = False
    for rule in rules:
        index = ordered.index(rule) if trigger in ("idle", "interval") else None
        lines, always = _rule_block(rule, index, returns, actions)
        body += lines
        unconditional |= always
    result = {"Verdict": "verdict", "bool": "handled"}.get(returns or "")
    if result and not any(line.strip().startswith(f"{result} =") for line in body):
        body.append("Verdict::Pass")  # buffer / event rules without verdicts
        result = None
    elif result:
        initial = "Verdict::Pass" if returns == "Verdict" else "false"
        body = [f"let mut {result} = {initial};", *body, result]
    params = [("core", "&Core"), ("ctx", "&Ctx"), *extra]
    signature = ", ".join(f"{n if uses_name(n, body) else '_' + n}: {t}" for n, t in params)
    arrow = f" -> {returns}" if returns else ""
    header = (
        ["    #[allow(unused_assignments)] // an unconditional rule decides alone"] if unconditional else []
    )
    return [
        "",
        *header,
        f"    fn {method}(&mut self, {signature}){arrow} {{",
        *[f"        {line}" for line in body],
        "    }",
    ]


def _needs_vars(rule_set: ProbeRuleSet) -> bool:
    uses = any(a.type in ("set-variable", "increment", "log") for r in rule_set.rules for a in r.actions)
    reads = any(c.type == "variable" for r in rule_set.rules for c in r.conditions)
    return bool(rule_set.variables) or uses or reads


def render_rule_set(
    rule_set: ProbeRuleSet, name: str, slots: dict[str, str], functions: dict[str, str]
) -> list[str]:
    value = RustValues(set(rule_set.variables))
    actions = RustActions(value, slots, functions)
    idle = [r for r in rule_set.rules if r.when.type == "idle"]
    intervals = [r for r in rule_set.rules if r.when.type == "interval"]
    target = rule_set.target
    lines = ["", f"/// Probe rule set {rust_str(rule_set.name)} on {target.kind} `{target.id}`."]
    if _needs_vars(rule_set):
        initial = [f"({rust_str(k)}, {value_literal(v)})," for k, v in rule_set.variables.items()]
        lines += [
            f"struct {name} {{",
            "    vars: Vars,",
            "}",
            "",
            f"impl {name} {{",
            "    fn new() -> Self {",
            f"        {name} {{",
            "            vars: Vars::new(&[",
            *[f"                {entry}" for entry in initial],
            "            ]),",
            "        }",
            "    }",
            "}",
        ]
    else:
        lines += [
            f"struct {name};",
            "",
            f"impl {name} {{",
            "    fn new() -> Self {",
            f"        {name}",
            "    }",
            "}",
        ]
    lines += [
        "",
        f"impl rt::Rules for {name} {{",
        f"    const NAME: &'static str = {rust_str(rule_set.name)};",
    ]
    if idle:
        lines.append(
            f"    const IDLE: &'static [u64] = &[{', '.join(str(r.when.ms or 1000) for r in idle)}];"
        )
    if intervals:
        ms = ", ".join(str(r.when.ms or 1000) for r in intervals)
        lines.append(f"    const INTERVALS: &'static [u64] = &[{ms}];")
    for trigger in _METHODS:
        rules = [r for r in rule_set.rules if r.when.type == trigger]
        if rules:
            ordered = idle if trigger == "idle" else intervals if trigger == "interval" else rules
            lines += _method(trigger, rules, ordered, actions)
    lines.append("}")
    return lines
