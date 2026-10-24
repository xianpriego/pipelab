"""Executes probe rule / API function actions (docs/DYNAMIC.md §4)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import gi

gi.require_version("GstVideo", "1.0")
from gi.repository import GstVideo

from pipelab.graph.probes import Action
from pipelab.gst import GLib, Gst
from pipelab.runtime.worker.builder import apply_property
from pipelab.runtime.worker.links import get_pad
from pipelab.runtime.worker.probe_values import expand, resolve, resolve_all


class Host(Protocol):
    """What actions need from the dynamic runtime."""

    def call(self, function: str, args: dict[str, Any]) -> Any: ...
    def signal(self, probe_id: str, name: str, value: Any) -> None: ...
    def slot_operation(self, operation: str, slot: str, params: dict[str, Any], instance: Any) -> Any: ...
    def log(self, probe_id: str, level: str, message: str) -> None: ...


class Owner(Protocol):
    """The rule set running the actions (None for API functions)."""

    probe_id: str

    def block(self) -> None: ...
    def unblock(self) -> None: ...
    def disable(self) -> None: ...


@dataclass
class ActionContext:
    scope: Any  # assembly.Scope the actions run in (element names are resolved there)
    env: dict[str, Any]  # variables + builtins (+ function arguments)
    variables: dict[str, Any] = field(default_factory=dict)
    pad: Gst.Pad | None = None  # pad of the current buffer/event
    pads: list[Gst.Pad] = field(default_factory=list)  # watched pads
    source: Gst.Element | None = None  # posts the application messages
    owner: Owner | None = None
    verdict: str | None = None  # "pass" / "drop" decided by the actions


def on_main_thread(function: Callable[[], Any]) -> None:
    """Topology changes and calls must not run in streaming threads."""
    if threading.current_thread() is threading.main_thread():
        function()
    else:
        GLib.idle_add(lambda: function() and False)


class ActionRunner:
    def __init__(self, host: Host) -> None:
        self._host = host

    def run(self, actions: list[Action], ctx: ActionContext) -> None:
        for action in actions:
            getattr(self, "_" + action.type.replace("-", "_"))(action, ctx)

    def _value(self, value: Any, ctx: ActionContext) -> Any:
        ctx.env.update(ctx.variables)
        return resolve(value, ctx.env)

    def _pad(self, action: Action, ctx: ActionContext) -> Gst.Pad | None:
        name = self._value(action.pad, ctx)
        if name:
            element = ctx.scope.element_named(action.node) if action.node else ctx.source
            return get_pad(element, str(name)) if element is not None else None
        return ctx.pad or (ctx.pads[0] if ctx.pads else None)

    def _pass(self, _action: Action, ctx: ActionContext) -> None:
        ctx.verdict = "pass"

    def _drop(self, _action: Action, ctx: ActionContext) -> None:
        ctx.verdict = "drop"

    def _block(self, _action: Action, ctx: ActionContext) -> None:
        if ctx.owner is not None:
            ctx.owner.block()

    def _unblock(self, _action: Action, ctx: ActionContext) -> None:
        if ctx.owner is not None:
            ctx.owner.unblock()

    def _remove_probe(self, _action: Action, ctx: ActionContext) -> None:
        if ctx.owner is not None:
            ctx.owner.disable()

    def _post_message(self, action: Action, ctx: ActionContext) -> None:
        structure = Gst.Structure.new_empty(action.name or "pipelab")
        for key, value in resolve_all(action.fields, {**ctx.env, **ctx.variables}).items():
            if value is not None:
                structure.set_value(key, value)
        if ctx.source is not None:
            ctx.source.post_message(Gst.Message.new_application(ctx.source, structure))

    def _set_property(self, action: Action, ctx: ActionContext) -> None:
        element = ctx.scope.element_named(action.node or "")
        target = get_pad(element, str(self._value(action.pad, ctx))) if element and action.pad else element
        if target is None:
            self._host.log(_probe_id(ctx), "warning", f"set-property: no element/pad '{action.node}'")
            return
        error = apply_property(target, action.property or "", self._value(action.value, ctx))
        if error:
            self._host.log(_probe_id(ctx), "warning", f"set-property: {error}")

    def _send_event(self, action: Action, ctx: ActionContext) -> None:
        pad = self._pad(action, ctx)
        if pad is None:
            return
        upstream = action.direction == "upstream"
        for event in _events(action, upstream, resolve_all(action.fields, {**ctx.env, **ctx.variables})):
            same_way = (pad.get_direction() == Gst.PadDirection.SRC) != upstream
            pad.push_event(event) if same_way else pad.send_event(event)

    def _request_keyframe(self, action: Action, ctx: ActionContext) -> None:
        pad = self._pad(action, ctx)
        if pad is not None:
            event = GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE, True, 0)
            pad.send_event(event) if pad.get_direction() == Gst.PadDirection.SRC else pad.push_event(event)

    def _set_variable(self, action: Action, ctx: ActionContext) -> None:
        ctx.variables[action.name or ""] = self._value(action.value, ctx)

    def _increment(self, action: Action, ctx: ActionContext) -> None:
        name = action.name or ""
        try:
            ctx.variables[name] = float(ctx.variables.get(name) or 0) + action.by
        except (TypeError, ValueError):
            ctx.variables[name] = action.by
        if float(ctx.variables[name]).is_integer():
            ctx.variables[name] = int(ctx.variables[name])

    def _log(self, action: Action, ctx: ActionContext) -> None:
        message = expand(action.message or "", {**ctx.env, **ctx.variables})
        self._host.log(_probe_id(ctx), action.level, message)

    def _signal(self, action: Action, ctx: ActionContext) -> None:
        target = action.probe or _probe_id(ctx)
        name, value = action.name or "", self._value(action.value, ctx)
        on_main_thread(lambda: self._host.signal(target, name, value))

    def _call(self, action: Action, ctx: ActionContext) -> None:
        args = resolve_all(action.args, {**ctx.env, **ctx.variables})
        on_main_thread(lambda: self._host.call(action.function or "", args))

    def _slot(self, operation: str, action: Action, ctx: ActionContext) -> None:
        params = resolve_all(action.params, {**ctx.env, **ctx.variables})
        instance = self._value(action.instance, ctx)
        on_main_thread(lambda: self._host.slot_operation(operation, action.slot or "", params, instance))

    def _add_instance(self, action: Action, ctx: ActionContext) -> None:
        self._slot("add", action, ctx)

    def _remove_instance(self, action: Action, ctx: ActionContext) -> None:
        self._slot("remove", action, ctx)

    def _restart_instance(self, action: Action, ctx: ActionContext) -> None:
        self._slot("restart", action, ctx)


def _probe_id(ctx: ActionContext) -> str:
    return ctx.owner.probe_id if ctx.owner is not None else "function"


def _events(action: Action, upstream: bool, fields: dict[str, Any]) -> list[Gst.Event]:
    if action.event == "eos":
        return [Gst.Event.new_eos()]
    if action.event == "flush":
        return [Gst.Event.new_flush_start(), Gst.Event.new_flush_stop(True)]
    if action.event == "force-key-unit":
        if upstream:
            return [GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE, True, 0)]
        return [
            GstVideo.video_event_new_downstream_force_key_unit(
                Gst.CLOCK_TIME_NONE, Gst.CLOCK_TIME_NONE, Gst.CLOCK_TIME_NONE, True, 0
            )
        ]
    structure = Gst.Structure.new_empty(action.name or "pipelab-event")
    for key, value in fields.items():
        if value is not None:
            structure.set_value(key, value)
    kind = Gst.EventType.CUSTOM_UPSTREAM if upstream else Gst.EventType.CUSTOM_DOWNSTREAM
    return [Gst.Event.new_custom(kind, structure)]
