"""``gst-launch-1.0`` rendering of a graph.

The DAG is covered with *chains* (``a ! b ! c``) made of links whose pads can
stay implicit. Every other link is written with references: prepended to a
chain (``t. ! queue ! …``), appended to it (``… ! mux.video_0``) or as a
standalone ``a.pad ! b.pad`` line. Elements are named only when referenced.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from pipelab.catalog.store import Catalog, is_template_name
from pipelab.export.common import ElementSpec, build_spec, identifier
from pipelab.graph.models import Edge, Graph, Node

_SAFE_VALUE = re.compile(r"^[\w.:/+\-@%]+$")
_SAFE_NAME = re.compile(r"^[A-Za-z_][\w\-]*$")
_TEMPLATE_TOKEN = re.compile(r"%[uds]")
_CAPS_SPACES = re.compile(r",\s+")


def _gst_quote(text: str) -> str:
    if _SAFE_VALUE.match(text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _shell_quote(text: str) -> str:
    if _SAFE_VALUE.match(text):
        return text
    for char in ("\\", '"', "$", "`"):
        text = text.replace(char, "\\" + char)
    return f'"{text}"'


def _compact_caps(caps: str) -> str:
    return _CAPS_SPACES.sub(",", caps.strip())


@dataclass
class _Plan:
    chain_next: dict[str, Edge] = field(default_factory=dict)
    chain_prev: dict[str, Edge] = field(default_factory=dict)
    prefix: dict[str, Edge] = field(default_factory=dict)
    suffix: dict[str, Edge] = field(default_factory=dict)
    standalone: list[Edge] = field(default_factory=list)
    referenced: set[str] = field(default_factory=set)
    inline_caps: set[str] = field(default_factory=set)


class _Renderer:
    def __init__(self, graph: Graph, catalog: Catalog, quote: Callable[[str], str], shell: bool) -> None:
        self.graph = graph
        self.catalog = catalog
        self.quote = quote
        self.shell = shell
        self.spec = build_spec(graph, catalog, "pipeline")
        self.elements = {e.node.id: e for e in self.spec.elements}
        self.order = [e.node.id for e in self.spec.elements]
        rank = {node_id: index for index, node_id in enumerate(self.order)}
        self.edges = sorted(
            (e for e in graph.edges if e.source in rank and e.target in rank),
            key=lambda e: (rank[e.source], rank[e.target], e.id),
        )
        self.plan = self._plan()
        self.names = self._reference_names()
        self._dynamic_index: dict[tuple[str, str], int] = {}

    def _node(self, node_id: str) -> Node:
        return self.elements[node_id].node

    def _implicit(self, node: Node, pad: str, direction: str) -> bool:
        """Whether gst-launch can pick this pad itself (``a ! b`` or ``name.``)."""
        element = self.catalog.get(node.factory)
        if element is None:
            return pad in ("src", "sink")
        templates = [t for t in element.pad_templates if t.direction == direction]
        template = self.catalog.pad_template(node.factory, pad)
        if len(templates) != 1 or template is None:
            return False
        if template.presence == "request":
            return not node.pad_properties and not self.elements[node.id].pad_refs
        return True

    def _chain_edge(self, edge: Edge) -> bool:
        return self._implicit(self._node(edge.source), edge.source_pad, "src") and self._implicit(
            self._node(edge.target), edge.target_pad, "sink"
        )

    def _closes_loop(self, plan: _Plan, edge: Edge) -> bool:
        current = edge.target
        while current in plan.chain_next:
            current = plan.chain_next[current].target
            if current == edge.source:
                return True
        return current == edge.source

    def _plan(self) -> _Plan:
        plan = _Plan()
        rest = []
        for edge in self.edges:
            free = edge.source not in plan.chain_next and edge.target not in plan.chain_prev
            if free and self._chain_edge(edge) and not self._closes_loop(plan, edge):
                plan.chain_next[edge.source] = edge
                plan.chain_prev[edge.target] = edge
            else:
                rest.append(edge)
        for edge in rest:
            target = self._node(edge.target)
            head = edge.target not in plan.chain_prev and edge.target not in plan.prefix
            if head and self._implicit(target, edge.target_pad, "sink"):
                plan.prefix[edge.target] = edge
                plan.referenced.add(edge.source)
                continue
            source = self._node(edge.source)
            tail = edge.source not in plan.chain_next and edge.source not in plan.suffix
            if tail and self._implicit(source, edge.source_pad, "src"):
                plan.suffix[edge.source] = edge
                plan.referenced.add(edge.target)
                continue
            plan.standalone.append(edge)
            plan.referenced.update((edge.source, edge.target))
        plan.inline_caps = {n for n in self.order if self._inline_caps(plan, n)}
        return plan

    def _inline_caps(self, plan: _Plan, node_id: str) -> bool:
        node = self._node(node_id)
        caps = node.properties.get("caps")
        plain = node.factory == "capsfilter" and set(node.properties) == {"caps"} and not node.pad_properties
        if not plain or not isinstance(caps, str) or not caps.strip() or node_id in plan.referenced:
            return False
        has_left = node_id in plan.chain_prev or node_id in plan.prefix
        has_right = node_id in plan.chain_next or node_id in plan.suffix
        return has_left and has_right

    def _reference_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for node_id in self.order:
            if node_id not in self.plan.referenced:
                continue
            name = self._node(node_id).name
            if not _SAFE_NAME.match(name) or name in names.values():
                name = identifier(name)
                while name in names.values():
                    name += "_"
            names[node_id] = name
        return names

    def _ref(self, node_id: str, pad: str, direction: str) -> str:
        node = self._node(node_id)
        name = self.names[node_id]
        if self._implicit(node, pad, direction):
            return f"{name}."
        if is_template_name(pad):
            index = self._dynamic_index.get((node_id, pad), 0)
            self._dynamic_index[(node_id, pad)] = index + 1
            pad = _TEMPLATE_TOKEN.sub(str(index), pad)
        return f"{name}.{pad}"

    def _caps(self, caps: str) -> str:
        compact = _compact_caps(caps)
        return _shell_quote(compact) if self.shell and not _SAFE_VALUE.match(compact) else compact

    def _declaration(self, element: ElementSpec) -> str:
        node = element.node
        if node.id in self.plan.inline_caps:
            return self._caps(str(node.properties["caps"]))
        tokens = [node.factory]
        if node.id in self.names:
            tokens.append(f"name={self.names[node.id]}")
        tokens += [f"{p.name}={self.quote(p.text)}" for p in element.properties]
        for pad, specs in element.pad_properties:
            tokens += [f"{pad}::{p.name}={self.quote(p.text)}" for p in specs]
        return " ".join(tokens)

    def _chain(self, head: str) -> str:
        parts = []
        if head in self.plan.prefix:
            edge = self.plan.prefix[head]
            parts.append(self._ref(edge.source, edge.source_pad, "src"))
        current: str | None = head
        tail = head
        while current is not None:
            parts.append(self._declaration(self.elements[current]))
            tail = current
            edge = self.plan.chain_next.get(current)
            current = edge.target if edge else None
        if tail in self.plan.suffix:
            edge = self.plan.suffix[tail]
            parts.append(self._ref(edge.target, edge.target_pad, "sink"))
        return " ! ".join(parts)

    def lines(self) -> list[str]:
        chains = [self._chain(n) for n in self.order if n not in self.plan.chain_prev]
        standalone = [
            f"{self._ref(e.source, e.source_pad, 'src')} ! {self._ref(e.target, e.target_pad, 'sink')}"
            for e in self.plan.standalone
        ]
        return chains + standalone

    def dropped_pad_properties(self) -> list[str]:
        return [f"{e.name}.{p.name}={p.text}" for e in self.spec.elements for p in e.pad_refs]


def render_description(graph: Graph, catalog: Catalog) -> str:
    """Single-line description for ``Gst.parse_launch`` (no shell quoting)."""
    return " ".join(_Renderer(graph, catalog, _gst_quote, shell=False).lines())


def render_command(graph: Graph, catalog: Catalog) -> str:
    """``gst-launch-1.0 -e`` command, one chain per line."""
    lines = _Renderer(graph, catalog, _shell_quote, shell=True).lines()
    body = " \\\n  ".join(lines)
    return f"gst-launch-1.0 -e \\\n  {body}" if body else "gst-launch-1.0 -e"


def render(graph: Graph, catalog: Catalog, name: str) -> str:
    renderer = _Renderer(graph, catalog, _shell_quote, shell=True)
    header = ["#!/bin/sh", f"# {name}: GStreamer pipeline generated by Pipelab."]
    dropped = renderer.dropped_pad_properties()
    if dropped:
        header.append("# Pad-typed properties cannot be set from gst-launch; set them in code:")
        header += [f"#   {item}" for item in dropped]
    return "\n".join(header) + "\n" + render_command(graph, catalog) + "\n"
