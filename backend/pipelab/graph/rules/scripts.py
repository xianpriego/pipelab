"""Rules about probe scripts: they must compile, define callbacks and have a target."""

from __future__ import annotations

import ast

from pipelab.graph.models import Issue, ProbeScript
from pipelab.graph.rules.base import RuleContext, issue

CALLBACKS = {"setup", "on_buffer", "on_event", "on_property", "on_trigger"}


def _script_issue(script: ProbeScript, severity: str, message: str) -> Issue:
    found = issue("script", severity, f"Script '{script.name}': {message}", key=f"{script.id}:{severity}")
    target = [script.target.id]
    return found.model_copy(
        update={"node_ids": target} if script.target.kind == "node" else {"edge_ids": target}
    )


def _check(ctx: RuleContext, script: ProbeScript) -> list[Issue]:
    exists = (
        ctx.graph.node(script.target.id) if script.target.kind == "node" else ctx.graph.edge(script.target.id)
    )
    if exists is None:
        return [_script_issue(script, "error", f"its {script.target.kind} no longer exists.")]
    try:
        tree = ast.parse(script.code, filename=script.name)
    except SyntaxError as error:
        return [_script_issue(script, "error", f"line {error.lineno}: {error.msg}.")]
    defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if not defined & CALLBACKS:
        return [_script_issue(script, "warning", "defines none of " + ", ".join(sorted(CALLBACKS)) + ".")]
    if script.target.kind == "edge" and "on_property" in defined:
        return [_script_issue(script, "warning", "on_property is only called for scripts on elements.")]
    return []


def scripts(ctx: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for script in ctx.graph.scripts:
        if script.enabled:
            issues += _check(ctx, script)
    return issues
