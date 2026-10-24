"""Commands sent by the API to a running worker (one JSON object per line)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pipelab.gst import GObject, Gst
from pipelab.gst.values import to_json_value
from pipelab.runtime.worker.control import dot_graph, read_properties, set_live_property
from pipelab.runtime.worker.dynamic import FunctionError
from pipelab.runtime.worker.slots import SlotError

if TYPE_CHECKING:
    from pipelab.runtime.worker.app import WorkerApp


def _current_value(element: Gst.Element, name: str) -> Any:
    pspec = element.find_property(name)
    if pspec is None or not pspec.flags & GObject.ParamFlags.READABLE:
        return None
    return to_json_value(element.get_property(name))


class CommandHandler:
    def __init__(self, app: WorkerApp) -> None:
        self.app = app

    def dispatch(self, command: dict[str, Any]) -> None:
        handler = getattr(self, f"cmd_{command.get('cmd', '')}", None)
        if handler is not None:
            handler(command)

    def _reply(self, command: dict[str, Any], data: dict[str, Any]) -> None:
        self.app.emit({"type": "reply", "request_id": command.get("request_id"), "data": data})

    def _element(self, command: dict[str, Any]) -> Gst.Element | None:
        return self.app.built.elements.get(command.get("node_id", ""))

    def cmd_play(self, _command: dict[str, Any]) -> None:
        self.app.built.pipeline.set_state(Gst.State.PLAYING)

    def cmd_pause(self, _command: dict[str, Any]) -> None:
        self.app.built.pipeline.set_state(Gst.State.PAUSED)

    def cmd_stop(self, command: dict[str, Any]) -> None:
        self.app.stop(command.get("mode", "eos"))

    def cmd_set_property(self, command: dict[str, Any]) -> None:
        element = self._element(command)
        name, value, pad = command["property"], command["value"], command.get("pad")
        if element is None:
            result: dict[str, Any] = {"ok": False, "error": "unknown element"}
        elif pad is None and self._intercepted(command["node_id"], name, value):
            result = {"ok": True, "deferred": True, "value": _current_value(element, name)}
        else:
            result = set_live_property(element, name, value, pad)
        self.app.emit(
            {
                "type": "property",
                "request_id": command.get("request_id"),
                "node_id": command.get("node_id"),
                "property": name,
                "pad": pad,
                **result,
            }
        )

    def _intercepted(self, node_id: str, name: str, value: Any) -> bool:
        """Scripts (on_property) and probe rules (property trigger) may take the change over."""
        if self.app.scripts.intercept(node_id, name, value):
            return True
        return self.app.dynamic is not None and self.app.dynamic.intercept(node_id, name, value)

    def cmd_get_properties(self, command: dict[str, Any]) -> None:
        element = self._element(command)
        self._reply(
            command, read_properties(element) if element is not None else {"error": "unknown element"}
        )

    def cmd_tap(self, command: dict[str, Any]) -> None:
        enabled = bool(command.get("enabled"))
        self._reply(command, self.app.instruments.set_tap(command.get("edge_id", ""), enabled))

    def cmd_probe(self, command: dict[str, Any]) -> None:
        enabled = bool(command.get("enabled"))
        self._reply(command, self.app.instruments.set_probe(command.get("edge_id", ""), enabled))

    def cmd_trigger(self, command: dict[str, Any]) -> None:
        self._reply(command, self.app.scripts.trigger(command.get("script_id", ""), command.get("value")))

    def cmd_call(self, command: dict[str, Any]) -> None:
        try:
            result = self.app.dynamic.call(command.get("function", ""), command.get("args") or {})
        except (FunctionError, SlotError, KeyError, TypeError, ValueError) as error:
            self._reply(command, {"ok": False, "error": str(error)})
            return
        self._reply(command, {"ok": True, "result": result})

    def cmd_signal(self, command: dict[str, Any]) -> None:
        try:
            self.app.dynamic.signal(command.get("probe", ""), command.get("name", ""), command.get("value"))
        except FunctionError as error:
            self._reply(command, {"ok": False, "error": str(error)})
            return
        self._reply(command, {"ok": True})

    def cmd_instances(self, command: dict[str, Any]) -> None:
        slots = self.app.dynamic.slots
        listing = {slot.id: slots.listing(slot.id) for slot in self.app.graph.slots} if slots else {}
        self._reply(command, {"slots": listing})

    def cmd_dot(self, command: dict[str, Any]) -> None:
        self._reply(command, {"dot": dot_graph(self.app.built.pipeline)})
