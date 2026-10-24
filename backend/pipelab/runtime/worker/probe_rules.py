"""Runs one probe rule set (docs/DYNAMIC.md §4) on its watched pads."""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from typing import Any

from pipelab.graph.probes import Condition, ProbeRule, ProbeRuleSet
from pipelab.gst import GLib, Gst
from pipelab.gst.values import to_json_value
from pipelab.runtime.worker.actions import ActionContext, ActionRunner, Host
from pipelab.runtime.worker.probe_values import compare, resolve

_FLAGS = {
    nick: value for value in Gst.BufferFlags.__flags_values__.values() for nick in (value.value_nicks or [])
}
_DATA = Gst.PadProbeType.BUFFER | Gst.PadProbeType.BUFFER_LIST
_SECOND = float(Gst.SECOND)


class RuleSetRuntime:
    def __init__(
        self,
        ruleset: ProbeRuleSet,
        probe_id: str,
        scope: Any,
        element: Gst.Element | None,
        runner: ActionRunner,
        host: Host,
        started: float,
    ) -> None:
        self.ruleset = ruleset
        self.probe_id = probe_id
        self.scope = scope
        self.element = element  # target element (node) or the owner of the probed pad (edge)
        self.variables: dict[str, Any] = dict(ruleset.variables)
        self.enabled = ruleset.enabled
        self._runner, self._host, self._started = runner, host, started
        self._lock = threading.RLock()
        self._pads: list[Gst.Pad] = []
        self._probes: list[tuple[Gst.Pad, int]] = []
        self._blocks: list[tuple[Gst.Pad, int]] = []
        self._timers: list[int] = []
        self._running_since: float | None = None
        self._last_data: float | None = None
        self._idle_fired: set[str] = set()
        self._every: dict[int, int] = {}
        self._window: deque[float] = deque()
        self._last_pts: dict[str, int] = {}

    def _rules(self, trigger: str) -> list[ProbeRule]:
        return [rule for rule in self.ruleset.rules if rule.when.type == trigger]

    # -- attaching -----------------------------------------------------------------
    def watch(self, pad: Gst.Pad) -> None:
        if pad in self._pads:
            return
        self._pads.append(pad)
        kinds = _DATA | Gst.PadProbeType.EVENT_DOWNSTREAM if self._rules("event") else _DATA
        self._probes.append((pad, pad.add_probe(kinds, self._on_probe)))

    def start(self) -> None:
        """Called once the pipeline (or the instance) is PLAYING."""
        if self._running_since is not None:
            return
        self._running_since = time.monotonic()
        self._fire("start", {})
        idle = [r.when.ms for r in self._rules("idle") if r.when.ms]
        if idle:
            self._timers.append(GLib.timeout_add(max(20, min(250, min(idle) // 4)), self._check_idle))
        for rule in self._rules("interval"):
            self._timers.append(GLib.timeout_add(max(10, rule.when.ms or 1000), self._on_interval, rule))

    def stop(self) -> None:
        for timer in self._timers:
            GLib.source_remove(timer)
        self._timers.clear()
        for pad, probe in self._probes + self._blocks:
            pad.remove_probe(probe)
        self._probes.clear()
        self._blocks.clear()

    # -- owner protocol used by actions -------------------------------------------
    def block(self) -> None:
        if not self._blocks:
            self._blocks = [
                (pad, pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, lambda *_: Gst.PadProbeReturn.OK))
                for pad in self._pads
            ]

    def unblock(self) -> None:
        for pad, probe in self._blocks:
            pad.remove_probe(probe)
        self._blocks.clear()

    def disable(self) -> None:
        self.enabled = False
        GLib.idle_add(lambda: self.stop() and False)

    # -- environment & conditions ------------------------------------------------------
    def _env(self, pad: Gst.Pad | None, buffer: Gst.Buffer | None, extra: dict[str, Any]) -> dict[str, Any]:
        env = {
            "time": round(time.monotonic() - self._started, 3),
            "instance": self.scope.instance,
            "node": self.element.get_name() if self.element else "",
            "pad": pad.get_name() if pad else None,
            "pts": None,
            "size": None,
            **extra,
        }
        if buffer is not None:
            env["pts"] = None if buffer.pts == Gst.CLOCK_TIME_NONE else buffer.pts / _SECOND
            env["size"] = buffer.get_size()
        return {**env, **self.variables}

    def _holds(
        self,
        rule: ProbeRule,
        cond: Condition,
        env: dict[str, Any],
        pad: Gst.Pad | None,
        buffer: Gst.Buffer | None,
    ) -> bool:
        value = resolve(cond.value, env)
        result: bool
        if cond.type == "keyframe":
            result = buffer is not None and not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)
        elif cond.type == "flag":
            result = buffer is not None and cond.flag in _FLAGS and buffer.has_flags(_FLAGS[cond.flag])
        elif cond.type == "size":
            result = buffer is not None and compare(buffer.get_size(), cond.op, value)
        elif cond.type in ("pts-gap", "pts-backwards"):
            result = self._pts_condition(cond, value, pad, buffer)
        elif cond.type == "every":
            key = id(cond)
            self._every[key] = self._every.get(key, 0) + 1
            result = self._every[key] % max(1, cond.n or 1) == 0
        elif cond.type == "rate":
            result = compare(len(self._window), cond.op, value)
        elif cond.type == "caps-field":
            result = self._caps_condition(cond, value, pad)
        elif cond.type == "variable":
            result = compare(self.variables.get(cond.name or ""), cond.op, value)
        elif cond.type == "pad":
            result = pad is not None and compare(pad.get_name(), cond.op, value)
        else:  # random
            result = random.random() * 100 < (cond.percent or 0)
        return result != cond.negate

    def _pts_condition(
        self, cond: Condition, value: Any, pad: Gst.Pad | None, buffer: Gst.Buffer | None
    ) -> bool:
        if buffer is None or pad is None or buffer.pts == Gst.CLOCK_TIME_NONE:
            return False
        previous = self._last_pts.get(pad.get_name())
        if previous is None:
            return False
        if cond.type == "pts-backwards":
            return buffer.pts < previous
        return compare((buffer.pts - previous) / 1e6, cond.op, value)

    def _caps_condition(self, cond: Condition, value: Any, pad: Gst.Pad | None) -> bool:
        caps = pad.get_current_caps() if pad is not None else None
        if caps is None or caps.is_empty() or not caps.get_structure(0).has_field(cond.field or ""):
            return False
        current = to_json_value(caps.get_structure(0).get_value(cond.field))
        return compare(current, cond.op, value)

    # -- firing ---------------------------------------------------------------------
    def _fire(
        self,
        trigger: str,
        extra: dict[str, Any],
        pad: Gst.Pad | None = None,
        buffer: Gst.Buffer | None = None,
        match: Any = None,
    ) -> str | None:
        """Run the rules of ``trigger``; returns the verdict of the last pass/drop."""
        if not self.enabled:
            return None
        verdict = None
        with self._lock:
            for rule in self._rules(trigger):
                if match is not None and not match(rule):
                    continue
                env = self._env(pad, buffer, extra)
                if not all(self._holds(rule, cond, env, pad, buffer) for cond in rule.conditions):
                    continue
                ctx = ActionContext(
                    scope=self.scope,
                    env=env,
                    variables=self.variables,
                    pad=pad,
                    pads=list(self._pads),
                    source=self.element,
                    owner=self,
                )
                self._runner.run(rule.actions, ctx)
                verdict = ctx.verdict or verdict or "matched"
        return verdict

    def _on_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        if info.type & Gst.PadProbeType.BUFFER:
            verdict = self._on_buffer(pad, info.get_buffer())
        elif info.type & Gst.PadProbeType.BUFFER_LIST:
            buffers = info.get_buffer_list()
            verdicts = [self._on_buffer(pad, buffers.get(i)) for i in range(buffers.length())]
            verdict = "drop" if "drop" in verdicts else None
        else:
            event = info.get_event()
            name = Gst.EventType.get_name(event.type)
            verdict = self._fire(
                "event", {"event": name}, pad, match=lambda r: r.when.event in (None, "any", name)
            )
        return Gst.PadProbeReturn.DROP if verdict == "drop" else Gst.PadProbeReturn.OK

    def _on_buffer(self, pad: Gst.Pad, buffer: Gst.Buffer) -> str | None:
        now = time.monotonic()
        with self._lock:
            resumed = bool(self._idle_fired)
            self._idle_fired.clear()
            self._last_data = now
            self._window.append(now)
            while self._window and now - self._window[0] > 1.0:
                self._window.popleft()
        if resumed:
            self._fire("resumed", {}, pad, buffer)
        verdict = self._fire("buffer", {}, pad, buffer)
        if buffer.pts != Gst.CLOCK_TIME_NONE:
            self._last_pts[pad.get_name()] = buffer.pts
        return verdict

    def _check_idle(self) -> bool:
        if self._running_since is None or not self.enabled:
            return GLib.SOURCE_CONTINUE
        with self._lock:
            idle_ms = (time.monotonic() - (self._last_data or self._running_since)) * 1000
            due = [
                r for r in self._rules("idle") if r.id not in self._idle_fired and idle_ms >= (r.when.ms or 0)
            ]
            self._idle_fired.update(rule.id for rule in due)
        for rule in due:
            self._fire("idle", {"idle_ms": round(idle_ms)}, match=lambda r, rule=rule: r is rule)
        return GLib.SOURCE_CONTINUE

    def _on_interval(self, rule: ProbeRule) -> bool:
        self._fire("interval", {}, match=lambda r: r is rule)
        return GLib.SOURCE_CONTINUE if self._timers else GLib.SOURCE_REMOVE

    # -- external triggers -------------------------------------------------------------
    def intercept(self, prop: str, value: Any) -> bool:
        """A live change of ``prop`` was requested: True if a rule took it over."""
        verdict = self._fire("property", {"value": value}, match=lambda r: r.when.property == prop)
        return verdict is not None and verdict != "pass"

    def signal(self, name: str, value: Any) -> None:
        self._fire("signal", {"value": value}, match=lambda r: r.when.name == name)
