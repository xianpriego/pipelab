"""Pipeline worker process: builds the graph, runs it and reports events.

Started by the API as ``python -m pipelab.runtime.worker`` with the media
directory as working directory. The first stdin line is the configuration
``{"graph": {...}, "components": {...}, "preview": {...}}``; the following
lines are commands (see ``commands.py``).
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from pipelab.components.models import Component
from pipelab.graph.models import Edge, Graph
from pipelab.gst import GLib, Gst
from pipelab.runtime.worker.assembly import Assembler, Scope
from pipelab.runtime.worker.builder import BuiltPipeline
from pipelab.runtime.worker.channel import Channel, start_command_reader
from pipelab.runtime.worker.commands import CommandHandler
from pipelab.runtime.worker.diagnose import find_negotiation_failure
from pipelab.runtime.worker.dynamic import DynamicRuntime
from pipelab.runtime.worker.encoder import PreviewSettings
from pipelab.runtime.worker.instruments import LinkInstruments
from pipelab.runtime.worker.messages import IGNORED, message_event
from pipelab.runtime.worker.monitor import LinkMonitor, query_time
from pipelab.runtime.worker.perf import QueueLevels, ThreadUsage
from pipelab.runtime.worker.previews import preview_kind
from pipelab.runtime.worker.script_host import ScriptHosts
from pipelab.runtime.worker.selectors import SelectorWatcher
from pipelab.runtime.worker.slots import SlotError, SlotManager

STOP_TIMEOUT_SECONDS = 6
_STATES = {Gst.State.READY: "ready", Gst.State.PAUSED: "paused", Gst.State.PLAYING: "playing"}


class WorkerApp:
    def __init__(self, config: dict[str, Any]) -> None:
        self.channel = Channel()
        self.graph = Graph.model_validate(config["graph"])
        self.components = {k: Component.model_validate(v) for k, v in config.get("components", {}).items()}
        self.preview = PreviewSettings(**config.get("preview", {}))
        self.loop = GLib.MainLoop()
        self.started = time.monotonic()
        self.stopping = self.failed = self.playing = False
        self.monitor = LinkMonitor(self.emit)
        self.queues = QueueLevels()
        self.threads = ThreadUsage()
        self.built = BuiltPipeline(pipeline=Gst.Pipeline.new("pipelab"))
        self.instruments = LinkInstruments(self.preview, self.started, self.emit)
        self.scripts = ScriptHosts(self.built.pipeline, self.emit, self.started)
        self.selectors = SelectorWatcher(self.emit)
        self.assembler = Assembler(self.components, self.preview, self.emit, self.built, self._on_linked)
        self.dynamic: DynamicRuntime | None = None
        self.commands = CommandHandler(self)

    def emit(self, event: dict[str, Any], payload: bytes = b"") -> None:
        self.channel.send(event, payload)

    def set_state(self, state: str, error: str | None = None) -> None:
        self.emit({"type": "state", "state": state, "error": error})

    def _report_errors(self, errors: list[tuple[Any, str]]) -> bool:
        for node, text in errors:
            self.emit(
                {
                    "type": "bus",
                    "kind": "error",
                    "source": node.name if node else None,
                    "node_id": node.id if node else None,
                    "text": text,
                    "time": 0.0,
                }
            )
        return bool(errors)

    # -- building ---------------------------------------------------------------------
    def build(self) -> bool:
        built = self.built
        top = self.assembler.build_scope(self.graph, built.pipeline)
        self.dynamic = DynamicRuntime(
            self.graph, self.components, built.pipeline, top, self.instruments.pads, self.emit, self.started
        )
        self.dynamic.slots = SlotManager(
            self.graph.slots,
            self.components,
            top,
            built.pipeline,
            self._build_slot_instance,
            self._on_instance,
            self._on_slot_link,
            self.emit,
        )
        static_scopes = list(built.scopes)
        if not built.errors:
            try:
                self.dynamic.slots.build_initial()
            except SlotError as error:
                built.errors.append((None, str(error)))
        for node, note in built.notes:
            self.emit({"type": "bus", "kind": "info", "source": node.name, "node_id": node.id, "text": note})
        if self._report_errors(built.errors):
            return False
        errors = [text for scope in static_scopes for text in self._attach_scope(scope)]
        return not self._report_errors([(None, text) for text in errors])

    def _build_slot_instance(
        self, name: str, component: Component, params: dict[str, Any], prefix: str
    ) -> Gst.Bin:
        """Build errors of a slot instance belong to the add operation, not to the whole pipeline."""
        known = len(self.built.errors)
        container = self.assembler.build_instance(name, component, params, prefix)
        errors = self.built.errors[known:]
        if errors:
            del self.built.errors[known:]
            self.built.scopes = [s for s in self.built.scopes if not s.prefix.startswith(prefix)]
            raise SlotError("; ".join(text for _node, text in errors))
        return container

    def _attach_scope(self, scope: Scope) -> list[str]:
        """Selector notifications, scripts and probe rules of one graph level."""
        previews = {node.id for node in scope.graph.nodes if preview_kind(node) is not None}
        self.selectors.watch(scope.graph, scope.elements, skip=previews, prefix=scope.prefix)
        for node in scope.graph.nodes:
            if node.id in scope.elements:
                self.queues.watch(scope.global_id(node.id), node.factory, scope.elements[node.id])
        errors = self.scripts.add_scope(scope, self.instruments.pads)
        self.dynamic.attach_scope(scope)
        return errors

    def _on_instance(self, prefix: str, added: bool) -> None:
        """A slot instance was built (before or while running) or removed."""
        if added:
            for scope in [s for s in self.built.scopes if s.prefix.startswith(prefix)]:
                self._report_errors([(None, text) for text in self._attach_scope(scope)])
            self.dynamic.start_prefix(prefix)
        else:
            self.dynamic.detach_prefix(prefix)
            self.scripts.remove_prefix(prefix)
            self.monitor.detach_prefix(prefix)
            self.queues.detach_prefix(prefix)
            self.built.scopes = [s for s in self.built.scopes if not s.prefix.startswith(prefix)]

    def _on_linked(self, edge_id: str, edge: Edge, src_pad: Gst.Pad) -> None:
        prefix = edge_id[: len(edge_id) - len(edge.id)]
        self.instruments.register(edge_id, src_pad)
        self.monitor.attach(edge_id, src_pad, f"{prefix}{edge.source}", f"{prefix}{edge.target}")
        self.scripts.on_linked(edge_id, src_pad)
        if self.dynamic is not None:
            self.dynamic.on_linked(edge_id, src_pad)

    def _on_slot_link(self, edge_id: str, src_pad: Gst.Pad) -> None:
        self.instruments.register(edge_id, src_pad)
        self.monitor.attach(edge_id, src_pad)

    # -- running ---------------------------------------------------------------------
    def run(self) -> int:
        self.set_state("starting")
        if not self.build():
            self.set_state("error", "the pipeline could not be built")
            return 1
        pipeline = self.built.pipeline
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)
        GLib.timeout_add(1000, self._report_stats)
        GLib.timeout_add(250, self.instruments.flush)
        start_command_reader(self.commands.dispatch, self.loop.quit)
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            # The bus messages explaining why are dispatched by the main loop:
            # only fall back to a generic reason if none arrives.
            GLib.timeout_add(500, self._report_start_failure)
        self.loop.run()
        self.dynamic.stop()
        self.instruments.close()
        pipeline.set_state(Gst.State.NULL)
        self.built.close_previews()
        self.set_state("stopped")
        return 0

    def _report_start_failure(self) -> bool:
        if not self.failed:
            self.failed = True
            self.set_state("error", "the pipeline refused to start (see the bus messages)")
        return GLib.SOURCE_REMOVE

    def _report_stats(self) -> bool:
        pipeline = self.built.pipeline
        self.emit(
            {
                "type": "stats",
                "time": round(time.monotonic() - self.started, 3),
                "position": query_time(pipeline, "position"),
                "duration": query_time(pipeline, "duration"),
                "edges": self.monitor.snapshot(),
                "elements": self.monitor.latency.snapshot(),
                "queues": self.queues.snapshot(),
                "threads": self.threads.snapshot(self.monitor.threads()),
            }
        )
        return GLib.SOURCE_CONTINUE

    def _on_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        if message.type in IGNORED:
            return
        pipeline = self.built.pipeline
        if message.type == Gst.MessageType.STATE_CHANGED and message.src != pipeline:
            return
        event = message_event(message, self.built.element_ids, self.started)
        if message.type == Gst.MessageType.ERROR and "not-negotiated" in (event.get("debug") or ""):
            self._explain_negotiation(event)
        self.emit(event)
        if message.type == Gst.MessageType.STATE_CHANGED:
            _old, new, _pending = message.parse_state_changed()
            if new in _STATES and not self.stopping and not self.failed:
                self.set_state(_STATES[new])
            if new == Gst.State.PLAYING and not self.playing:
                self.playing = True
                self.dynamic.start()
        elif message.type == Gst.MessageType.ERROR:
            if not self.failed:
                self.failed = True
                self.set_state("error", message.parse_error()[0].message)
        elif message.type == Gst.MessageType.EOS:
            self.loop.quit()
        elif message.type == Gst.MessageType.LATENCY:
            pipeline.recalculate_latency()
        elif message.type == Gst.MessageType.CLOCK_LOST:
            pipeline.set_state(Gst.State.PAUSED)
            pipeline.set_state(Gst.State.PLAYING)

    def _explain_negotiation(self, event: dict[str, Any]) -> None:
        """Point a not-negotiated error at the link and caps field that caused it."""
        names = {}
        for scope in self.built.scopes:
            where = f"{scope.instance}/" if scope.instance else ""
            for edge in scope.graph.edges:
                source, target = scope.graph.node(edge.source), scope.graph.node(edge.target)
                names[scope.global_id(edge.id)] = (
                    f"{where}{source.name}.{edge.source_pad}",
                    f"{where}{target.name}.{edge.target_pad}",
                )
        failure = find_negotiation_failure(self.instruments.pads, names)
        if failure is not None:
            event["edge_id"] = failure.edge_id
            event["hint"] = (
                f"Caps negotiation failed on {failure.text} Insert a converter/scaler or adapt the caps."
            )

    def stop(self, mode: str) -> None:
        """``kill`` quits at once; ``eos`` drains the pipeline so files get finalised."""
        if mode == "kill" or self.stopping:
            self.loop.quit()
            return
        self.stopping = True
        self.set_state("stopping")
        pipeline = self.built.pipeline
        if pipeline.get_state(0)[1] != Gst.State.PLAYING:
            pipeline.set_state(Gst.State.PLAYING)
        pipeline.send_event(Gst.Event.new_eos())
        GLib.timeout_add_seconds(STOP_TIMEOUT_SECONDS, self._force_quit)

    def _force_quit(self) -> bool:
        self.emit(
            {"type": "bus", "kind": "warning", "text": "EOS did not reach the sinks in time; stopped anyway"}
        )
        self.loop.quit()
        return GLib.SOURCE_REMOVE


def main() -> None:
    config = json.loads(sys.stdin.readline())
    sys.exit(WorkerApp(config).run())
