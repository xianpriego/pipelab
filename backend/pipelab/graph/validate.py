"""Whole-graph validation: runs every rule and orders the issues."""

from __future__ import annotations

import logging

from pipelab.graph.analyzer import Analyzer
from pipelab.graph.models import Graph, Issue
from pipelab.graph.rules import RULES, RuleContext

log = logging.getLogger(__name__)
_ORDER = {"error": 0, "warning": 1, "info": 2}


def validate_graph(analyzer: Analyzer, graph: Graph) -> list[Issue]:
    ctx = RuleContext(graph, analyzer)
    issues: dict[str, Issue] = {}
    for rule in RULES:
        try:
            found = rule(ctx)
        except Exception:  # one faulty rule must not hide the others
            log.exception("validation rule %s failed", rule.__name__)
            continue
        for item in found:
            issues.setdefault(item.id, item)
    return sorted(issues.values(), key=lambda i: _ORDER[i.severity])
