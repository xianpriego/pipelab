"""Embedded Python support: probe host and the base class of generated rule sets."""

RULES = '''

BUILTINS = ("value", "pad", "pts", "size", "time", "instance", "node", "idle_ms")


class ProbeContext:
    """What triggered a rule: the pad, buffer or event, and the trigger value."""

    def __init__(self, pad=None, buffer=None, event=None, value=None, prop=None, idle_ms=None, name=None):
        self.pad, self.buffer, self.event = pad, buffer, event
        self.value, self.property, self.idle_ms, self.name = value, prop, idle_ms, name

    @property
    def pad_name(self):
        return self.pad.get_name() if self.pad is not None else None

    @property
    def pts(self):
        if self.buffer is None or self.buffer.pts == Gst.CLOCK_TIME_NONE:
            return None
        return self.buffer.pts / Gst.SECOND

    @property
    def size(self):
        return self.buffer.get_size() if self.buffer is not None else None


class ProbeHost:
    """Rule sets of one pipeline: started together, reachable by id, deferring work to the main loop."""

    def __init__(self, dispatch=None) -> None:
        self.rule_sets: dict = {}
        self.started = False
        self._dispatch = dispatch

    def register(self, rule_set) -> None:
        self.rule_sets[rule_set.probe_id] = rule_set
        if self.started:
            rule_set.start()

    def start(self) -> None:
        if not self.started:
            self.started = True
            for rule_set in list(self.rule_sets.values()):
                rule_set.start()

    def defer(self, kind: str, *args) -> None:
        """call / add / remove / restart / signal run on the main loop, never in a streaming thread."""

        def run() -> bool:
            if kind == "signal":
                target = self.rule_sets.get(args[0])
                if target is not None:
                    target.signal(args[1], args[2])
            elif self._dispatch is not None:
                self._dispatch(kind, *args)
            else:
                print(f"no pipeline to run '{kind}' {args}", file=sys.stderr)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(run)


class RuleSet:
    """Wiring shared by generated rule sets: watched pads, timers, verdicts, actions."""

    NAME = "probe"
    IDLE: tuple = ()  # ms of each idle rule
    INTERVALS: tuple = ()  # ms of each interval rule
    VARIABLES: dict = {}

    def __init__(self, host, elements, element, pad, kind, probe_id, instance="", node=""):
        self.host, self.elements, self.kind = host, elements, kind
        self.element = elements[element]
        self.pad_spec, self.probe_id = pad, probe_id
        self.instance, self.node = instance, node
        self.vars = dict(self.VARIABLES)
        self.enabled = True
        self.lock = threading.RLock()
        self.pads: list = []
        self.blocks: dict = {}
        self.counters: dict = {}
        self.arrivals: list = []
        self.last_pts = None
        self.gap_ms = None
        self.backwards = False
        self.started_at = None
        self.last_buffer = None
        self.idle_fired = [False] * len(self.IDLE)

    # wiring
    def attach(self) -> None:
        for pad in self.element.pads:
            self._maybe_watch(pad)
        self.element.connect("pad-added", lambda _element, pad: self._maybe_watch(pad))
        self.host.register(self)

    def _maybe_watch(self, pad: Gst.Pad) -> None:
        if pad in self.pads:
            return
        if self.pad_spec is not None:
            wanted = matches(pad, self.pad_spec)
        else:
            wanted = pad.get_direction() == Gst.PadDirection.SINK
        if wanted:
            self.pads.append(pad)
            kinds = Gst.PadProbeType.BUFFER | Gst.PadProbeType.BUFFER_LIST | Gst.PadProbeType.EVENT_DOWNSTREAM
            pad.add_probe(kinds, self._on_probe)

    def start(self) -> None:
        with self.lock:
            self.started_at = self.last_buffer = time.monotonic()
        for index, ms in enumerate(self.IDLE):
            GLib.timeout_add(max(10, min(ms // 4, 100)), self._check_idle, index, ms)
        for index, ms in enumerate(self.INTERVALS):
            GLib.timeout_add(ms, self._tick, index)
        self._run(lambda: self.on_start(ProbeContext()))

    def _run(self, rules):
        with self.lock:
            if self.enabled:
                return rules()
        return None

    def _check_idle(self, index: int, ms: int) -> bool:
        if not self.enabled:
            return GLib.SOURCE_REMOVE
        with self.lock:
            idle = (time.monotonic() - self.last_buffer) * 1000
            if idle >= ms and not self.idle_fired[index]:
                self.idle_fired[index] = True
                self.on_idle(ProbeContext(idle_ms=round(idle)), index)
        return GLib.SOURCE_CONTINUE

    def _tick(self, index: int) -> bool:
        if not self.enabled:
            return GLib.SOURCE_REMOVE
        self._run(lambda: self.on_interval(ProbeContext(), index))
        return GLib.SOURCE_CONTINUE

    def _on_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        if not self.enabled or self.started_at is None:
            return Gst.PadProbeReturn.OK
        if info.type & Gst.PadProbeType.EVENT_DOWNSTREAM:
            event = info.get_event()
            name = Gst.EventType.get_name(event.type)
            verdict = self._run(lambda: self.on_event(ProbeContext(pad=pad, event=event, value=name), name))
            return Gst.PadProbeReturn.DROP if verdict == DROP else Gst.PadProbeReturn.OK
        buffers = [info.get_buffer()] if info.type & Gst.PadProbeType.BUFFER else []
        if info.type & Gst.PadProbeType.BUFFER_LIST:
            listed = info.get_buffer_list()
            buffers = [listed.get(i) for i in range(listed.length())]
        verdicts = [self._run(lambda b=buffer: self._buffer(pad, b)) for buffer in buffers]
        return Gst.PadProbeReturn.DROP if DROP in verdicts else Gst.PadProbeReturn.OK

    def _buffer(self, pad: Gst.Pad, buffer: Gst.Buffer):
        now = time.monotonic()
        self.arrivals = [t for t in self.arrivals if now - t < 1.0] + [now]
        pts = None if buffer.pts == Gst.CLOCK_TIME_NONE else buffer.pts
        known = pts is not None and self.last_pts is not None
        self.gap_ms = (pts - self.last_pts) / Gst.MSECOND if known else None
        self.backwards = self.gap_ms is not None and self.gap_ms < 0
        self.last_pts = pts if pts is not None else self.last_pts
        self.last_buffer = now
        ctx = ProbeContext(pad=pad, buffer=buffer)
        if any(self.idle_fired):
            self.idle_fired = [False] * len(self.IDLE)
            self.on_resumed(ctx)
        return self.on_buffer(ctx)

    def sibling(self, probe: str) -> str:
        """Id of another rule set of the same scope (instance)."""
        return f"{self.instance}/{probe}" if self.instance else probe

    # entry points from the owner (main loop)
    def signal(self, name: str, value=None) -> None:
        self._run(lambda: self.on_signal(ProbeContext(value=value, name=name), name))

    def offer_property(self, element: str, prop: str, value) -> bool:
        """True when a rule intercepted the change (it must not be applied now)."""
        if element != (f"{self.instance}/{self.node}" if self.instance else self.node):
            return False
        return bool(self._run(lambda: self.on_property(ProbeContext(value=value, prop=prop), prop)))

    # generated rule sets override these
    def on_start(self, ctx): return None
    def on_buffer(self, ctx): return PASS
    def on_event(self, ctx, event): return PASS
    def on_idle(self, ctx, index): return None
    def on_resumed(self, ctx): return None
    def on_interval(self, ctx, index): return None
    def on_property(self, ctx, prop): return False
    def on_signal(self, ctx, name): return None

    # builtins and conditions
    def builtin(self, name: str, ctx: ProbeContext):
        values = {
            "value": ctx.value, "pad": ctx.pad_name, "pts": ctx.pts, "size": ctx.size,
            "time": time.monotonic() - self.started_at if self.started_at else 0.0,
            "instance": self.instance, "node": self.node, "idle_ms": ctx.idle_ms,
        }
        return values.get(name)

    def is_keyframe(self, ctx) -> bool:
        return ctx.buffer is not None and not ctx.buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)

    def has_flag(self, ctx, flag: str) -> bool:
        if ctx.buffer is None:
            return False
        return bool(ctx.buffer.get_flags() & getattr(Gst.BufferFlags, flag.upper().replace("-", "_")))

    def every(self, key: str, n: int) -> bool:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key] % max(n, 1) == 0

    def rate(self) -> float:
        return float(len(self.arrivals))

    def caps_field(self, ctx, field: str):
        pad = ctx.pad or (self.pads[0] if self.pads else None)
        caps = pad.get_current_caps() if pad is not None else None
        if caps is None or caps.get_size() == 0 or not caps.get_structure(0).has_field(field):
            return None
        value = caps.get_structure(0).get_value(field)
        return value if isinstance(value, bool | int | float | str) else Gst.value_serialize(value)

    def chance(self, percent: float) -> bool:
        return random.random() * 100 < percent

    # actions
    def _pad(self, name, ctx):
        if name:
            return pad_of(self.element, str(name))[0]
        return ctx.pad or (self.pads[0] if self.pads else None)

    def post(self, name: str, fields: dict) -> None:
        self.element.post_message(Gst.Message.new_application(self.element, structure(name, fields)))

    def set_property(self, node: str, prop: str, value, pad=None) -> None:
        apply_value(self.elements[node], prop, value, pad)

    def send(self, kind: str, downstream: bool, ctx, pad=None, name=None, fields=None) -> None:
        target = self._pad(pad, ctx)
        if target is not None:
            send_event(target, make_event(kind, downstream, name, fields), downstream)

    def request_keyframe(self, ctx, pad=None) -> None:
        self.send("force-key-unit", False, ctx, pad)

    def block(self) -> None:
        for pad in self.pads:
            if pad not in self.blocks:
                hold = lambda *_: Gst.PadProbeReturn.OK  # noqa: E731
                self.blocks[pad] = pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, hold)

    def unblock(self) -> None:
        for pad, probe in list(self.blocks.items()):
            pad.remove_probe(probe)
        self.blocks.clear()

    def remove(self) -> None:
        self.enabled = False
        self.unblock()

    def log(self, message: str, level: str, ctx) -> None:
        values = {**{k: self.builtin(k, ctx) for k in BUILTINS}, **self.vars}
        try:
            text = message.format(**values)
        except (KeyError, IndexError, ValueError):
            text = message
        print(f"[{self.NAME}] {level}: {text}", file=sys.stderr)
'''
