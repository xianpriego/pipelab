"""Commands sent by the API to a running worker (one JSON object per line)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pipelab.gst import Gst
from pipelab.runtime.worker.control import dot_graph, read_properties, set_live_property

if TYPE_CHECKING:
    from pipelab.runtime.worker.app import WorkerApp


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

    def cmd_dot(self, command: dict[str, Any]) -> None:
        self._reply(command, {"dot": dot_graph(self.app.built.pipeline)})
