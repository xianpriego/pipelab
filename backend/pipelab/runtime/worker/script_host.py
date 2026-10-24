"""Runs the probe scripts of a graph inside the worker.

Each enabled script is compiled into its own namespace, gets a ``ScriptContext``
and has its ``on_buffer``/``on_event`` callbacks installed as pad probes on the
link's source pad (edge scripts) or on the element's pads (node scripts).
A failing callback never breaks the pipeline: the data passes and the error is
reported once per callback.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipelab.graph.models import Graph, ProbeScript
from pipelab.gst import GLib, Gst
from pipelab.runtime.worker.script_context import DROP, PASS, REMOVE, ScriptContext

_RETURNS = {DROP: Gst.PadProbeReturn.DROP, REMOVE: Gst.PadProbeReturn.REMOVE}
_WATCH = {"sink": Gst.PadDirection.SINK, "src": Gst.PadDirection.SRC}


@dataclass
class _Loaded:
    script: ProbeScript
    namespace: dict[str, Any]
    ctx: ScriptContext
    failures: set[str] = field(default_factory=set)

    def handler(self, name: str) -> Callable[..., Any] | None:
        function = self.namespace.get(name)
        return function if callable(function) else None


class ScriptHost:
    def __init__(
        self,
        graph: Graph,
        pipeline: Gst.Pipeline,
        elements: dict[str, Gst.Element],
        node_names: dict[str, str],
        emit: Callable[[dict[str, Any]], None],
        started: float,
    ) -> None:
        self._graph = graph
        self._pipeline = pipeline
        self._elements = elements
        self._by_name = {
            name: elements[node_id] for name, node_id in node_names.items() if node_id in elements
        }
        self._emit = emit
        self._started = started
        self._scripts: dict[str, _Loaded] = {}
        self._pending_edges: dict[str, list[_Loaded]] = {}

    def load(self, edge_pads: dict[str, Gst.Pad]) -> list[str]:
        """Compile, attach and ``setup`` every enabled script; returns error messages."""
        errors = []
        for script in self._graph.scripts:
            if not script.enabled:
                continue
            try:
                loaded = self._compile(script)
            except Exception as error:  # noqa: BLE001 - shown to the user as a build error
                errors.append(f"Script '{script.name}': {type(error).__name__}: {error}")
                continue
            self._scripts[script.id] = loaded
            self._attach(loaded, edge_pads)
            self._call(loaded, "setup", loaded.ctx)
        return errors

    def _compile(self, script: ProbeScript) -> _Loaded:
        code = compile(script.code, f"<script {script.name}>", "exec")
        namespace: dict[str, Any] = {
            "Gst": Gst,
            "GLib": GLib,
            "PASS": PASS,
            "DROP": DROP,
            "REMOVE": REMOVE,
            "__name__": f"pipelab_script_{script.id}",
        }
        exec(code, namespace)
        element = self._elements.get(script.target.id) if script.target.kind == "node" else None
        if script.target.kind == "node" and element is None:
            raise LookupError("its element is not in the pipeline")
        ctx = ScriptContext(
            script.id, script.name, self._pipeline, self._by_name, self._emit, self._started, element=element
        )
        return _Loaded(script, namespace, ctx)

    def _attach(self, loaded: _Loaded, edge_pads: dict[str, Gst.Pad]) -> None:
        target = loaded.script.target
        if target.kind == "edge":
            pad = edge_pads.get(target.id)
            if pad is None:  # dynamic link: attached when the pad appears
                self._pending_edges.setdefault(target.id, []).append(loaded)
            else:
                self._bind_pad(loaded, pad)
            return
        element = loaded.ctx.element
        watch = str(loaded.namespace.get("WATCH", "sink"))
        for pad in element.pads:
            if watch == "all" or pad.get_direction() == _WATCH.get(watch):
                self._probe(loaded, pad)
        element.connect("pad-added", lambda _e, pad: self._probe_new_pad(loaded, pad, watch))

    def _probe_new_pad(self, loaded: _Loaded, pad: Gst.Pad, watch: str) -> None:
        if watch == "all" or pad.get_direction() == _WATCH.get(watch):
            self._probe(loaded, pad)

    def on_linked(self, edge_id: str, pad: Gst.Pad) -> None:
        for loaded in self._pending_edges.pop(edge_id, []):
            self._bind_pad(loaded, pad)

    def _bind_pad(self, loaded: _Loaded, pad: Gst.Pad) -> None:
        loaded.ctx.pad, loaded.ctx.element = pad, pad.get_parent_element()
        self._probe(loaded, pad)

    def _probe(self, loaded: _Loaded, pad: Gst.Pad) -> None:
        on_buffer, on_event = loaded.handler("on_buffer"), loaded.handler("on_event")
        kinds = Gst.PadProbeType(0)
        if on_buffer:
            kinds |= Gst.PadProbeType.BUFFER | Gst.PadProbeType.BUFFER_LIST
        if on_event:
            kinds |= Gst.PadProbeType.EVENT_DOWNSTREAM
        if kinds:
            pad.add_probe(kinds, self._on_probe, loaded)

    def _on_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo, loaded: _Loaded) -> Gst.PadProbeReturn:
        if info.type & Gst.PadProbeType.BUFFER:
            result = self._call(loaded, "on_buffer", loaded.ctx, pad, info.get_buffer())
        elif info.type & Gst.PadProbeType.BUFFER_LIST:
            buffers = info.get_buffer_list()
            results = [
                self._call(loaded, "on_buffer", loaded.ctx, pad, buffers.get(i))
                for i in range(buffers.length())
            ]
            result = DROP if DROP in results else (REMOVE if REMOVE in results else PASS)
        else:
            result = self._call(loaded, "on_event", loaded.ctx, pad, info.get_event())
        return _RETURNS.get(result, Gst.PadProbeReturn.OK)

    def _call(self, loaded: _Loaded, name: str, *args: Any) -> Any:
        function = loaded.handler(name)
        if function is None:
            return None
        try:
            return function(*args)
        except Exception as error:  # noqa: BLE001 - user code must not break the pipeline
            if name not in loaded.failures:
                loaded.failures.add(name)
                where = traceback.extract_tb(error.__traceback__)[-1]
                loaded.ctx.log(
                    f"{name} failed at line {where.lineno}: {type(error).__name__}: {error}", level="error"
                )
            return None

    def intercept(self, node_id: str, prop: str, value: Any) -> bool:
        """Offer a live property change to the node's scripts; True if one took it."""
        candidates = [
            loaded
            for loaded in self._scripts.values()
            if loaded.script.target.kind == "node" and loaded.script.target.id == node_id
        ]
        return any(self._call(loaded, "on_property", loaded.ctx, prop, value) for loaded in candidates)

    def has(self, script_id: str) -> bool:
        return script_id in self._scripts

    def trigger(self, script_id: str, value: Any) -> dict[str, Any]:
        loaded = self._scripts.get(script_id)
        if loaded is None:
            return {"ok": False, "error": "the script is not running (disabled or failed to load)"}
        if loaded.handler("on_trigger") is None:
            return {"ok": False, "error": "the script has no on_trigger(ctx, value)"}
        loaded.failures.discard("on_trigger")
        self._call(loaded, "on_trigger", loaded.ctx, value)
        failed = "on_trigger" in loaded.failures
        return {
            "ok": not failed,
            **({"error": "on_trigger raised an error (see the Probe tab)"} if failed else {}),
        }


class ScriptHosts:
    """One ScriptHost per graph scope (top level and component instances)."""

    def __init__(
        self, pipeline: Gst.Pipeline, emit: Callable[[dict[str, Any]], None], started: float
    ) -> None:
        self._pipeline, self._emit, self._started = pipeline, emit, started
        self._hosts: list[tuple[str, ScriptHost]] = []

    @staticmethod
    def _local(prefix: str, global_id: str) -> str | None:
        rest = global_id[len(prefix) :] if global_id.startswith(prefix) else None
        return rest if rest is not None and "/" not in rest else None

    def add_scope(self, scope: Any, edge_pads: dict[str, Gst.Pad]) -> list[str]:
        if not scope.graph.scripts:
            return []
        names = {node.name: node.id for node in scope.graph.nodes}
        host = ScriptHost(scope.graph, self._pipeline, scope.elements, names, self._emit, self._started)
        pads = {local: pad for gid, pad in edge_pads.items() if (local := self._local(scope.prefix, gid))}
        self._hosts.append((scope.prefix, host))
        return host.load(pads)

    def remove_prefix(self, prefix: str) -> None:
        self._hosts = [(p, h) for p, h in self._hosts if not p.startswith(prefix)]

    def on_linked(self, edge_id: str, pad: Gst.Pad) -> None:
        for prefix, host in self._hosts:
            if (local := self._local(prefix, edge_id)) is not None:
                host.on_linked(local, pad)

    def intercept(self, node_id: str, prop: str, value: Any) -> bool:
        return any(
            host.intercept(local, prop, value)
            for prefix, host in self._hosts
            if (local := self._local(prefix, node_id)) is not None
        )

    def trigger(self, script_id: str, value: Any) -> dict[str, Any]:
        for prefix, host in self._hosts:
            local = self._local(prefix, script_id) or (script_id if prefix == "" else None)
            if local is not None and host.has(local):
                return host.trigger(local, value)
        return {"ok": False, "error": "the script is not running (disabled or failed to load)"}
