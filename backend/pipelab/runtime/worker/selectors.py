"""Reports changes of GstPad-typed properties (input-selector ``active-pad``…).

Selectors pick their first pad by themselves and may switch for other reasons,
so the UI learns the pad really in use from ``notify`` instead of guessing.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from pipelab.graph.models import Graph
from pipelab.gst import GObject, Gst

Emit = Callable[[dict[str, Any]], None]


class SelectorWatcher:
    def __init__(self, emit: Emit) -> None:
        self._emit = emit
        self._last: dict[tuple[str, str], str | None] = {}
        self._lock = threading.Lock()

    def watch(self, graph: Graph, elements: dict[str, Gst.Element], skip: set[str], prefix: str = "") -> None:
        for node in graph.nodes:
            element = elements.get(node.id)
            if element is None or node.id in skip or isinstance(element, Gst.Bin):
                continue
            for pspec in element.list_properties():
                writable = pspec.flags & GObject.ParamFlags.WRITABLE
                if writable and pspec.value_type.is_a(Gst.Pad.__gtype__):
                    element.connect(f"notify::{pspec.name}", self._on_notify, prefix + node.id)

    def _on_notify(self, element: Gst.Element, pspec: GObject.ParamSpec, node_id: str) -> None:
        pad = element.get_property(pspec.name)
        value = pad.get_name() if pad is not None else None
        with self._lock:
            if self._last.get((node_id, pspec.name), "") == value:
                return
            self._last[(node_id, pspec.name)] = value
        self._emit(
            {
                "type": "property",
                "node_id": node_id,
                "property": pspec.name,
                "value": value,
                "ok": True,
                "origin": "runtime",
            }
        )
