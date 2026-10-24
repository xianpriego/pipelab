"""The pipeline class of the Python library: static graph, slots, API functions, bus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pipelab.export.plan import FunctionPlan, ProgramPlan, SlotPlan
from pipelab.export.python_probes import ValueRenderer, literal
from pipelab.graph.models import Graph
from pipelab.graph.probes import Action

if TYPE_CHECKING:
    from pipelab.export.python_dynamic import ScopeRenderer

_PY_TYPES = {"string": "str", "int": "int", "float": "float", "bool": "bool"}

_LIFECYCLE = '''
    def start(self) -> None:
        """Set the pipeline to PLAYING (a GLib main loop must run to dispatch the bus)."""
        if self.pipeline is None:
            self.build()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus)
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("the pipeline refused to start")

    def stop(self) -> None:
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline.get_bus().remove_signal_watch()

    def send_eos(self) -> None:
        """Ask sources to finish so muxers and files are finalised cleanly."""
        if self.pipeline is not None:
            self.pipeline.send_event(Gst.Event.new_eos())

    def on_message(self, callback) -> None:
        """``callback(name, fields, source)`` for every application message (probe rules)."""
        self._callbacks.append(callback)

    def set_element_property(self, element: str, name: str, value) -> bool:
        """Change a property; probe rules on that element may intercept it (returns True)."""
        for rule_set in list(self.host.rule_sets.values()):
            if rule_set.offer_property(element, name, value):
                return True
        apply_value(self.element(element), name, value)
        return False

    def signal(self, probe: str, name: str, value=None) -> None:
        """Fire the ``signal`` rules of a probe (``<instance>/<probe>`` inside components)."""
        self.host.rule_sets[probe].signal(name, value)

    def element(self, path: str) -> Gst.Element:
        """``name`` or ``instance/inner`` for elements inside components."""
        first, *rest = path.split("/")
        element = self.elements.get(first) or self.pipeline.get_by_name(first)
        for part in rest:
            element = element.get_by_name(part)
        if element is None:
            raise KeyError(f"no element {path}")
        return element

    def _elapsed(self) -> float:
        return time.monotonic() - self._started if self._started else 0.0

    def _post(self, name: str, fields: dict) -> None:
        self.pipeline.post_message(Gst.Message.new_application(self.pipeline, structure(name, fields)))

    def _dispatch(self, kind: str, *args) -> None:
        """Work deferred by probe rules to the main loop."""
        if kind == "call":
            getattr(self, args[0])(**args[1])
        elif kind == "add":
            self.slots[args[0]].add(args[1])
        elif kind == "remove":
            self.slots[args[0]].remove(args[1])
        elif kind == "restart":
            self.slots[args[0]].restart(args[1])

    def _on_bus(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        kind = message.type
        if kind == Gst.MessageType.APPLICATION:
            data = message.get_structure()
            names = [data.nth_field_name(i) for i in range(data.n_fields())]
            fields = {key: data.get_value(key) for key in names}
            source = message.src.get_name() if message.src is not None else None
            for callback in self._callbacks:
                callback(data.get_name(), fields, source)
        elif kind == Gst.MessageType.STATE_CHANGED and message.src == self.pipeline:
            if message.parse_state_changed()[1] == Gst.State.PLAYING and not self.host.started:
                self._started = time.monotonic()
                self.host.start()
        elif kind == Gst.MessageType.ELEMENT and message.has_name("GstBinForwarded"):
            forwarded = message.get_structure().get_value("message")
            if forwarded.type == Gst.MessageType.EOS:
                for slot in self.slots.values():
                    slot.forwarded_eos(forwarded.src)
        elif kind == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            print(f"ERROR from {message.src.get_path_string()}: {error.message}\\n  {debug}", file=sys.stderr)
            self.exit_code = 1
            self._quit()
        elif kind == Gst.MessageType.EOS:
            self._quit()

    def _quit(self) -> None:
        if self.loop is not None:
            self.loop.quit()

    def run(self) -> int:
        """Play until end-of-stream or error; Ctrl+C sends EOS first."""
        self.loop = GLib.MainLoop()
        self.start()
        interrupt = lambda *_: self.send_eos() or GLib.SOURCE_CONTINUE  # noqa: E731
        unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, interrupt)
        try:
            self.loop.run()
        finally:
            self.stop()
        return self.exit_code
'''


def _slot_defaults(slot: SlotPlan) -> str:
    entries = [{"id": i.id, **i.params} for i in slot.slot.initial]
    return f"{slot.slot.name!r}: {entries!r}"


def _slot_links(slot: SlotPlan, names: dict[str, str]) -> str:
    """(port, direction, element name, pad, pad properties) per link, as SlotManager expects."""
    ports = {p.name: p for p in slot.component.ports}
    links = []
    for link in slot.slot.links:
        direction = ports[link.port].direction if link.port in ports else "src"
        links.append(
            (link.port, direction, names.get(link.node_id, link.node_id), link.pad, link.pad_properties)
        )
    return repr(links)


def _slot_methods(slot: SlotPlan) -> list[str]:
    params = slot.component.params
    keywords = "".join(f", {p.ident}: {_PY_TYPES[p.kind]} | None = None" for p in params)
    values = ", ".join(f"{p.ident!r}: {p.ident}" for p in params)
    key = repr(slot.slot.id)
    title = slot.component.component.name
    return [
        "",
        f"    def add_{slot.item}(self, *{keywords}, instance_id: str | None = None) -> str:",
        f'        """Add a {title} to {slot.slot.name!r}; returns its id."""',
        f"        params = {{key: value for key, value in {{{values}}}.items() if value is not None}}",
        f"        return self.slots[{key}].add(params, instance_id)",
        "",
        f"    def remove_{slot.item}(self, instance_id: str) -> None:",
        f"        self.slots[{key}].remove(instance_id)",
        "",
        f"    def restart_{slot.item}(self, instance_id: str) -> str:",
        f"        return self.slots[{key}].restart(instance_id)",
        "",
        f"    def list_{slot.ident}(self) -> list[dict]:",
        f"        return self.slots[{key}].list()",
    ]


def _function_action(action: Action, value: ValueRenderer, program: ProgramPlan) -> list[str]:
    slots = {s.slot.id: s for s in program.slots} | {s.slot.name: s for s in program.slots}
    kind = action.type
    if kind == "set-property":
        if action.pad is not None:
            return [
                f"apply_value(self.element({action.node or ''!r}), {action.property or ''!r}, "
                f"{value(action.value)}, {value(action.pad)})"
            ]
        return [
            f"self.set_element_property({action.node or ''!r}, {action.property or ''!r}, "
            f"{value(action.value)})"
        ]
    if kind == "post-message":
        return [f"self._post({action.name or 'message'!r}, {value.mapping(action.fields)})"]
    if kind in ("send-event", "request-keyframe"):
        event = action.event or "eos" if kind == "send-event" else "force-key-unit"
        downstream = action.direction == "downstream" if kind == "send-event" else False
        events = f"make_event({event!r}, {downstream}, {action.name!r}, {value.mapping(action.fields)})"
        return [f"send_to(self.element({action.node or ''!r}), {value(action.pad)}, {events}, {downstream})"]
    if kind == "log":
        text = repr(f"{action.level}: {action.message or ''}")
        values = value.mapping({p: "$" + p for p in sorted(value.params)})
        return [f"print(expand({text}, {values}), file=sys.stderr)"]
    if kind == "signal":
        return [f"self.signal({action.probe or ''!r}, {action.name or ''!r}, {value(action.value)})"]
    if kind == "call":
        return [f"self.{action.function}(**{value.mapping(action.args)})"]
    if kind in ("add-instance", "remove-instance", "restart-instance") and action.slot in slots:
        key = repr(slots[action.slot].slot.id)
        if kind == "add-instance":
            return [f"self.slots[{key}].add({value.mapping(action.params)})"]
        operation = "remove" if kind == "remove-instance" else "restart"
        return [f"self.slots[{key}].{operation}({value(action.instance)})"]
    return [f"# {kind}: not applicable in a function"]


def _function_method(function: FunctionPlan, program: ProgramPlan) -> list[str]:
    params = function.function.params
    value = ValueRenderer(set(), {p.name for p in params}, scope="function")
    signature = "".join(f", {p.name}: {_PY_TYPES[p.type]} = {literal(p.default)}" for p in params)
    lines = ["", f"    def {function.ident}(self{signature}) -> None:"]
    lines.append(f'        """{function.function.description or function.function.name}"""')
    body = [line for action in function.function.actions for line in _function_action(action, value, program)]
    return lines + [f"        {line}" for line in body or ["pass"]]


def render_pipeline_class(
    program: ProgramPlan, graph: Graph, renderer: ScopeRenderer, scripts: bool
) -> list[str]:
    names = {node.id: node.name for node in graph.nodes}
    cls = f"{program.type_name}Pipeline"
    base = "(ProbeScriptsMixin)" if scripts else ""
    defaults = ", ".join(_slot_defaults(s) for s in program.slots)
    build = [
        "self.pipeline = Gst.Pipeline.new(" + literal(program.name) + ")",
        *(['self.pipeline.set_property("message-forward", True)'] if program.message_forward else []),
        "container, elements = self.pipeline, self.elements",
        *(["host = self.host"] if program.root.probes or program.root.instances else []),
        *renderer.elements(program.root),
        *renderer.links(program.root),
        *renderer.probes(program.root, graph, ""),
    ]
    for slot in program.slots:
        build.append(
            f"self.slots[{slot.slot.id!r}] = SlotManager("
            f"self, {slot.slot.item!r}, build_{slot.component.ident}, "
            f"{_slot_links(slot, names)}, {slot.slot.max_instances!r})"
        )
        build += [
            f"for entry in self.config.get({slot.slot.name!r}, self.INITIAL[{slot.slot.name!r}]):",
            "    params = {key: value for key, value in entry.items() if key != 'id'}",
            f"    self.slots[{slot.slot.id!r}].add(params, entry.get('id'))",
        ]
    if scripts:
        build.append("self._attach_scripts()")
    build.append("return self.pipeline")
    lines = [
        "",
        "",
        f"class {cls}{base}:",
        f'    """{program.name}: owns the pipeline, its dynamic parts and the bus."""',
        "",
        f"    INITIAL = {{{defaults}}}",
        "",
        "    def __init__(self, config: dict | None = None) -> None:",
        "        self.config = config or {}",
        "        self.pipeline: Gst.Pipeline | None = None",
        "        self.elements: dict[str, Gst.Element] = {}",
        "        self.host = ProbeHost(self._dispatch)",
        "        self.slots: dict[str, SlotManager] = {}",
        "        self._callbacks: list = []",
        "        self._started = None",
        "        self.loop: GLib.MainLoop | None = None",
        "        self.exit_code = 0",
        "",
        "    def build(self) -> Gst.Pipeline:",
        '        """Create the static graph, its probes and the initial slot instances."""',
        *[f"        {line}" for line in build],
        _LIFECYCLE.rstrip("\n"),
    ]
    for slot in program.slots:
        lines += _slot_methods(slot)
    for function in program.functions:
        lines += _function_method(function, program)
    lines += [
        "",
        "",
        "def main() -> int:",
        "    Gst.init(sys.argv)",
        f"    pipeline = {cls}()",
        "    pipeline.on_message(",
        '        lambda name, fields, source: print(f"message {name} from {source}: {fields}")',
        "    )",
        "    return pipeline.run()",
        "",
        "",
        'if __name__ == "__main__":',
        "    sys.exit(main())",
    ]
    return lines
