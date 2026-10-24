"""The ``ctx`` object handed to probe script callbacks."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("GstVideo", "1.0")

from gi.repository import GstVideo

from pipelab.gst import Gst
from pipelab.runtime.worker.builder import apply_property

PASS, DROP, REMOVE = "pass", "drop", "remove"
LOGS_PER_SECOND = 50

Emit = Callable[[dict[str, Any]], None]


class ScriptContext:
    """What a script can see and do. ``state`` survives between callbacks."""

    def __init__(
        self,
        script_id: str,
        name: str,
        pipeline: Gst.Pipeline,
        elements: dict[str, Gst.Element],
        emit: Emit,
        started: float,
        element: Gst.Element | None = None,
        pad: Gst.Pad | None = None,
    ) -> None:
        self.script_id = script_id
        self.name = name
        self.pipeline = pipeline
        self.element = element
        self.pad = pad
        self.state: dict[str, Any] = {}
        self._elements = elements
        self._emit = emit
        self._started = started
        self._window = (0.0, 0)

    def get(self, name: str) -> Gst.Element | None:
        """Element of the pipeline by its (node) name."""
        return self._elements.get(name)

    def pad_named(self, name: str, element: Gst.Element | str | None = None) -> Gst.Pad | None:
        owner = self.get(element) if isinstance(element, str) else (element or self.element)
        return owner.get_static_pad(name) if owner is not None else None

    def is_keyframe(self, buffer: Gst.Buffer) -> bool:
        return not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)

    def set(self, element_name: str, prop: str, value: Any) -> None:
        """Set a property like gst-launch does (pad-typed properties take a pad name)."""
        element = self.get(element_name)
        if element is None:
            raise KeyError(f"no element named '{element_name}'")
        error = apply_property(element, prop, value)
        if error:
            raise ValueError(error)

    def request_keyframe(self, pad: Gst.Pad | str | None = None, all_headers: bool = True) -> bool:
        """Ask the encoder upstream of ``pad`` (default: the probed pad) for a key unit."""
        target = self.pad_named(pad) if isinstance(pad, str) else (pad or self.pad)
        if target is None:
            raise ValueError("request_keyframe needs a pad")
        event = GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE, all_headers, 0)
        if target.get_direction() == Gst.PadDirection.SRC:
            return target.send_event(event)
        return target.push_event(event)

    def log(self, message: str, level: str = "info", **fields: Any) -> None:
        now = time.monotonic()
        start, count = self._window
        if now - start >= 1.0:
            start, count = now, 0
        if count >= LOGS_PER_SECOND:
            return
        self._window = (start, count + 1)
        event = {
            "type": "script",
            "script_id": self.script_id,
            "name": self.name,
            "level": level,
            "message": str(message),
            "time": round(now - self._started, 3),
        }
        if fields:
            event["fields"] = {
                k: v if isinstance(v, str | int | float | bool) else str(v) for k, v in fields.items()
            }
        self._emit(event)
