"""Probe rule sets, slots and API functions of a running pipeline."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pipelab.components.models import Component
from pipelab.graph.dynamic import ApiFunction
from pipelab.graph.models import Graph
from pipelab.gst import Gst
from pipelab.runtime.worker.actions import ActionContext, ActionRunner
from pipelab.runtime.worker.probe_rules import RuleSetRuntime
from pipelab.runtime.worker.slots import SlotError, SlotManager

Emit = Callable[[dict[str, Any]], None]


class FunctionError(ValueError):
    pass


class DynamicRuntime:
    """Implements ``actions.Host`` for the rule sets and functions it owns."""

    def __init__(
        self,
        graph: Graph,
        components: dict[str, Component],
        pipeline: Gst.Pipeline,
        top: Any,
        edge_pads: dict[str, Gst.Pad],
        emit: Emit,
        started: float,
    ) -> None:
        self._graph = graph
        self._pipeline = pipeline
        self._top = top
        self._edge_pads = edge_pads  # global edge id → source pad (filled while linking)
        self._emit = emit
        self._started = started
        self._functions: dict[str, ApiFunction] = {f.name: f for f in graph.functions}
        self._rulesets: dict[str, RuleSetRuntime] = {}
        self._pending_edges: dict[str, list[RuleSetRuntime]] = {}
        self.runner = ActionRunner(self)
        self.slots: SlotManager | None = None
        self.components = components
        self.running = False

    # -- rule sets -----------------------------------------------------------------
    def attach_scope(self, scope: Any) -> None:
        for ruleset in scope.graph.probes:
            if not ruleset.enabled:
                continue
            probe_id = scope.global_id(ruleset.id)
            target = ruleset.target
            element = scope.elements.get(target.id) if target.kind == "node" else None
            runtime = RuleSetRuntime(ruleset, probe_id, scope, element, self.runner, self, self._started)
            self._rulesets[probe_id] = runtime
            if target.kind == "edge":
                self._watch_edge(runtime, scope.global_id(target.id))
            elif element is not None:
                self._watch_element(runtime, element, target.pad)
            if self.running:
                runtime.start()

    def _watch_edge(self, runtime: RuleSetRuntime, edge_id: str) -> None:
        pad = self._edge_pads.get(edge_id)
        if pad is None:  # dynamic link: watched when linked
            self._pending_edges.setdefault(edge_id, []).append(runtime)
            return
        runtime.element = runtime.element or pad.get_parent_element()
        runtime.watch(pad)

    def on_linked(self, edge_id: str, pad: Gst.Pad) -> None:
        for runtime in self._pending_edges.pop(edge_id, []):
            runtime.element = runtime.element or pad.get_parent_element()
            runtime.watch(pad)

    def _watch_element(self, runtime: RuleSetRuntime, element: Gst.Element, pad_name: str | None) -> None:
        def wanted(pad: Gst.Pad) -> bool:
            if pad_name is None:
                return pad.get_direction() == Gst.PadDirection.SINK
            template = pad.get_pad_template()
            return pad_name in (pad.get_name(), template.name_template if template else None)

        for pad in element.pads:
            if wanted(pad):
                runtime.watch(pad)
        element.connect("pad-added", lambda _e, pad: wanted(pad) and runtime.watch(pad))

    def detach_prefix(self, prefix: str) -> None:
        for probe_id in [p for p in self._rulesets if p.startswith(prefix)]:
            self._rulesets.pop(probe_id).stop()

    def start(self) -> None:
        self.running = True
        if self.slots is not None:
            self.slots.running = True
        for runtime in list(self._rulesets.values()):
            runtime.start()

    def start_prefix(self, prefix: str) -> None:
        if self.running:
            for probe_id, runtime in list(self._rulesets.items()):
                if probe_id.startswith(prefix):
                    runtime.start()

    def stop(self) -> None:
        for runtime in self._rulesets.values():
            runtime.stop()

    def intercept(self, node_id: str, prop: str, value: Any) -> bool:
        targets = [
            r
            for r in self._rulesets.values()
            if r.ruleset.target.kind == "node" and r.scope.global_id(r.ruleset.target.id) == node_id
        ]
        return any([runtime.intercept(prop, value) for runtime in targets])

    # -- actions.Host --------------------------------------------------------------------
    def signal(self, probe_id: str, name: str, value: Any) -> None:
        runtime = self._rulesets.get(probe_id) or next(
            (
                r
                for key, r in self._rulesets.items()
                if key.endswith(f"/{probe_id}") or r.ruleset.id == probe_id
            ),
            None,
        )
        if runtime is None:
            raise FunctionError(f"unknown probe '{probe_id}'")
        runtime.signal(name, value)

    def log(self, probe_id: str, level: str, message: str) -> None:
        self._emit(
            {
                "type": "probe-log",
                "probe": probe_id,
                "level": level,
                "message": message,
                "time": round(time.monotonic() - self._started, 3),
            }
        )

    def slot_operation(self, operation: str, slot: str, params: dict[str, Any], instance: Any) -> Any:
        if self.slots is None:
            raise SlotError("this pipeline has no slots")
        if operation == "add":
            return self.slots.add(slot, params)
        if operation == "remove":
            return self.slots.remove(slot, str(instance))
        return self.slots.restart(slot, str(instance))

    def call(self, function: str, args: dict[str, Any]) -> Any:
        builtin = self._builtin(function)
        if builtin is not None:
            return builtin(args)
        definition = self._functions.get(function)
        if definition is None:
            raise FunctionError(f"unknown function '{function}'")
        env = {param.name: args.get(param.name, param.default) for param in definition.params}
        ctx = ActionContext(scope=self._top, env=dict(env), source=self._pipeline)
        self.runner.run(definition.actions, ctx)
        return None

    def _builtin(self, function: str) -> Callable[[dict[str, Any]], Any] | None:
        if self.slots is None:
            return None
        for slot in self._graph.slots:
            if function == f"add_{slot.item}":
                return lambda args, s=slot: self.slots.add(
                    s.id, {k: v for k, v in args.items() if k != "id"}, args.get("id")
                )
            if function == f"remove_{slot.item}":
                return lambda args, s=slot: self.slots.remove(s.id, str(args.get("id")))
            if function == f"restart_{slot.item}":
                return lambda args, s=slot: self.slots.restart(s.id, str(args.get("id")))
            if function == f"list_{slot.name}":
                return lambda _args, s=slot: self.slots.listing(s.id)
        return None
