"""Rules for slots, pipeline functions and probe rule sets (docs/DYNAMIC.md)."""

from __future__ import annotations

import re

from pipelab.graph.link_check import check_link
from pipelab.graph.models import Edge, Graph, Issue, Node
from pipelab.graph.probes import Action, ProbeRuleSet
from pipelab.graph.rules.base import RuleContext, issue

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
BUILTINS = {"value", "pad", "pts", "size", "time", "instance", "node", "idle_ms", "index", "id"}
_NEEDS = {"idle": "ms", "interval": "ms", "event": "event", "property": "property", "signal": "name"}


def builtin_functions(graph: Graph) -> set[str]:
    names = set()
    for slot in graph.slots:
        names |= {f"add_{slot.item}", f"remove_{slot.item}", f"restart_{slot.item}", f"list_{slot.name}"}
    return names


def _slot_issue(slot, message: str, severity: str = "error", key: str = "") -> Issue:
    return issue("slot", severity, f"Slot '{slot.name}': {message}", key=f"{slot.id}{key}")


def slots(ctx: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[str] = set()
    for slot in ctx.graph.slots:
        for name in (slot.name, slot.item):
            if not IDENTIFIER.match(name):
                issues.append(
                    _slot_issue(
                        slot, f"'{name}' must be a lowercase identifier (it names functions).", key=f":{name}"
                    )
                )
        if {slot.name, slot.item} & seen:
            issues.append(_slot_issue(slot, "its name or item is already used by another slot.", key=":dup"))
        seen |= {slot.name, slot.item}
        component = ctx.analyzer.components.get(slot.component)
        if component is None:
            issues.append(
                _slot_issue(slot, f"component '{slot.component}' is not in the library.", key=":component")
            )
            continue
        params = {p.name for p in component.parameters}
        for initial in slot.initial:
            for unknown in sorted(set(initial.params) - params):
                issues.append(
                    _slot_issue(
                        slot,
                        f"'{unknown}' is not a parameter of {component.name}.",
                        "warning",
                        f":{initial.id}:{unknown}",
                    )
                )
        issues += _slot_links(ctx, slot, component)
    return issues


def _slot_links(ctx: RuleContext, slot, component) -> list[Issue]:
    issues = []
    ports = {p.name: p for p in component.ports}
    for link in slot.links:
        key = f"{slot.id}:{link.port}:{link.node_id}"
        port, target = ports.get(link.port), ctx.graph.node(link.node_id)
        if port is None or target is None:
            missing = f"port '{link.port}'" if port is None else f"element '{link.node_id}'"
            issues.append(issue("slot", "error", f"Slot '{slot.name}': {missing} does not exist.", key=key))
            continue
        probe = Node(id="__slot__", factory=component.factory, name=f"{slot.item}0")
        graph = ctx.graph.model_copy(update={"nodes": [*ctx.graph.nodes, probe]})
        edge = (
            Edge(id="__slot__", source=probe.id, source_pad=port.name, target=target.id, target_pad=link.pad)
            if port.direction == "src"
            else Edge(
                id="__slot__", source=target.id, source_pad=link.pad, target=probe.id, target_pad=port.name
            )
        )
        result = check_link(ctx.analyzer, graph, edge)
        for found in result.issues:
            if found.severity == "error":
                issues.append(
                    issue("slot", "error", f"Slot '{slot.name}': {found.message}", [target], key=key)
                )
    return issues


def functions(ctx: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    builtins = builtin_functions(ctx.graph)
    seen: set[str] = set()
    for function in ctx.graph.functions:
        prefix = f"Function '{function.name}'"
        if not IDENTIFIER.match(function.name):
            issues.append(
                issue(
                    "function",
                    "error",
                    f"{prefix}: the name must be a lowercase identifier.",
                    key=f"{function.name}:name",
                )
            )
        if function.name in seen or function.name in builtins:
            issues.append(
                issue("function", "error", f"{prefix}: the name is already used.", key=f"{function.name}:dup")
            )
        seen.add(function.name)
        known = {p.name for p in function.params} | BUILTINS
        issues += _actions(ctx, function.actions, prefix, known, f"function:{function.name}")
    return issues


def probes(ctx: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for ruleset in ctx.graph.probes:
        if ruleset.enabled:
            issues += _ruleset(ctx, ruleset)
    return issues


def _ruleset(ctx: RuleContext, ruleset: ProbeRuleSet) -> list[Issue]:
    prefix = f"Probe '{ruleset.name}'"
    target = ruleset.target
    node = ctx.graph.node(target.id) if target.kind == "node" else None
    if (target.kind == "node" and node is None) or (
        target.kind == "edge" and ctx.graph.edge(target.id) is None
    ):
        return [issue("probe", "error", f"{prefix}: its {target.kind} no longer exists.", key=ruleset.id)]
    issues = []
    if (
        node is not None
        and target.pad
        and ctx.analyzer.catalog.pad_template(node.factory, target.pad) is None
    ):
        issues.append(
            issue(
                "probe",
                "error",
                f"{prefix}: '{node.name}' has no pad '{target.pad}'.",
                [node],
                key=f"{ruleset.id}:pad",
            )
        )
    known = set(ruleset.variables) | BUILTINS
    for rule in ruleset.rules:
        needed = _NEEDS.get(rule.when.type)
        if needed and not getattr(rule.when, needed):
            issues.append(
                issue(
                    "probe",
                    "error",
                    f"{prefix}: the '{rule.when.type}' trigger needs '{needed}'.",
                    key=f"{ruleset.id}:{rule.id}:trigger",
                )
            )
        if rule.when.type == "property" and target.kind != "node":
            issues.append(
                issue(
                    "probe",
                    "warning",
                    f"{prefix}: property triggers only work on elements.",
                    key=f"{ruleset.id}:{rule.id}:property",
                )
            )
        known |= {a.name for a in rule.actions if a.type in ("set-variable", "increment") and a.name}
        issues += _actions(ctx, rule.actions, prefix, known, f"{ruleset.id}:{rule.id}")
    return issues


def _references(action: Action) -> list[str]:
    values = [
        action.value,
        action.pad,
        action.instance,
        *action.fields.values(),
        *action.args.values(),
        *action.params.values(),
    ]
    return [v[1:] for v in values if isinstance(v, str) and v.startswith("$") and not v.startswith("$$")]


def _actions(ctx: RuleContext, actions: list[Action], prefix: str, known: set[str], key: str) -> list[Issue]:
    issues = []
    names = {n.name: n for n in ctx.graph.nodes}
    functions = {f.name for f in ctx.graph.functions} | builtin_functions(ctx.graph)
    slot_ids = {s.id for s in ctx.graph.slots} | {s.name for s in ctx.graph.slots}
    for index, action in enumerate(actions):
        problem = None
        if action.type in ("set-property",) and action.node not in names:
            problem = f"element '{action.node}' does not exist"
        elif action.type == "set-property":
            element = ctx.analyzer.catalog.get(names[action.node].factory)
            if element is not None and not action.pad and element.property(action.property or "") is None:
                problem = f"'{action.node}' has no property '{action.property}'"
        elif action.type == "call" and action.function not in functions:
            problem = f"function '{action.function}' does not exist"
        elif (
            action.type in ("add-instance", "remove-instance", "restart-instance")
            and action.slot not in slot_ids
        ):
            problem = f"slot '{action.slot}' does not exist"
        elif action.type in ("post-message", "set-variable", "increment", "signal") and not action.name:
            problem = f"the '{action.type}' action needs a name"
        if problem:
            issues.append(
                issue(
                    "probe" if not key.startswith("function:") else "function",
                    "error",
                    f"{prefix}: {problem}.",
                    key=f"{key}:{index}",
                )
            )
        for reference in _references(action):
            if reference not in known:
                issues.append(
                    issue(
                        "probe" if not key.startswith("function:") else "function",
                        "warning",
                        f"{prefix}: unknown reference '${reference}'.",
                        key=f"{key}:{index}:{reference}",
                    )
                )
    return issues
