"""Probe scripts in the exported Python program (same callbacks as in Pipelab)."""

from __future__ import annotations

from pipelab.graph.models import Graph, ProbeScript

HARNESS = '''

# --- Probe scripts ------------------------------------------------------------
# Same contract as in Pipelab: setup(ctx), on_buffer(ctx, pad, buffer),
# on_event(ctx, pad, event), on_property(ctx, name, value) -> bool and
# on_trigger(ctx, value); return PASS, DROP or REMOVE from the probes.
import traceback  # noqa: E402

gi.require_version("GstVideo", "1.0")
from gi.repository import GstVideo  # noqa: E402

PASS, DROP, REMOVE = "pass", "drop", "remove"
_PROBE_RETURNS = {DROP: Gst.PadProbeReturn.DROP, REMOVE: Gst.PadProbeReturn.REMOVE}


class ScriptContext:
    def __init__(self, name, elements, element=None, pad=None):
        self.name, self.elements, self.element, self.pad = name, elements, element, pad
        self.state = {}

    def get(self, name):
        return self.elements.get(name)

    def pad_named(self, name, element=None):
        owner = self.get(element) if isinstance(element, str) else (element or self.element)
        return owner.get_static_pad(name) if owner is not None else None

    def is_keyframe(self, buffer):
        return not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)

    def set(self, element_name, prop, value):
        element = self.get(element_name)
        pspec = element.find_property(prop)
        if pspec is not None and pspec.value_type.is_a(Gst.Pad.__gtype__):
            element.set_property(prop, element.get_static_pad(str(value)))
        else:
            text = str(value).lower() if isinstance(value, bool) else str(value)
            Gst.util_set_object_arg(element, prop, text)

    def request_keyframe(self, pad=None, all_headers=True):
        target = self.pad_named(pad) if isinstance(pad, str) else (pad or self.pad)
        event = GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE, all_headers, 0)
        if target.get_direction() == Gst.PadDirection.SRC:
            return target.send_event(event)
        return target.push_event(event)

    def log(self, message, level="info", **fields):
        extra = " ".join(f"{key}={value}" for key, value in fields.items())
        print(f"[{self.name}] {level}: {message} {extra}".rstrip(), file=sys.stderr)


class ProbeScriptsMixin:
    """Attaches PROBE_SCRIPTS; set_property() and trigger() mirror the Pipelab UI."""

    def _attach_scripts(self):
        self._scripts = []
        for script in PROBE_SCRIPTS:
            namespace = {"Gst": Gst, "GLib": GLib, "PASS": PASS, "DROP": DROP, "REMOVE": REMOVE}
            exec(compile(script["code"], f"<script {script['name']}>", "exec"), namespace)  # noqa: S102
            kind, element_name, pad_name = script["target"]
            element = self.elements[element_name]
            entry = (script, namespace, ScriptContext(script["name"], self.elements, element=element))
            self._scripts.append(entry)
            if kind == "link":
                self._probe_link(entry, element, pad_name)
            else:
                watch = namespace.get("WATCH", "sink")
                for pad in element.pads:
                    self._maybe_probe(entry, pad, watch)
                element.connect("pad-added", self._on_pad_added, entry, watch)
            self._call(entry, "setup", entry[2])

    def _on_pad_added(self, _element, pad, entry, watch):
        self._maybe_probe(entry, pad, watch)

    def _probe_link(self, entry, element, pad_name):
        pad = element.get_static_pad(pad_name)
        if pad is not None:
            self._bind(entry, pad)
            return

        def on_pad_added(_element, new_pad):  # sometimes pads appear while running
            template = new_pad.get_pad_template()
            matches = new_pad.get_name() == pad_name or (template and template.name_template == pad_name)
            if matches and entry[2].pad is None:
                self._bind(entry, new_pad)

        element.connect("pad-added", on_pad_added)

    def _bind(self, entry, pad):
        entry[2].pad, entry[2].element = pad, pad.get_parent_element()
        self._add_probe(entry, pad)

    def _maybe_probe(self, entry, pad, watch):
        is_src = pad.get_direction() == Gst.PadDirection.SRC
        if watch == "all" or (watch == "src") == is_src:
            self._add_probe(entry, pad)

    def _add_probe(self, entry, pad):
        namespace = entry[1]
        kinds = Gst.PadProbeType(0)
        if callable(namespace.get("on_buffer")):
            kinds |= Gst.PadProbeType.BUFFER
        if callable(namespace.get("on_event")):
            kinds |= Gst.PadProbeType.EVENT_DOWNSTREAM
        if kinds:
            pad.add_probe(kinds, self._on_probe, entry)

    def _on_probe(self, pad, info, entry):
        if info.type & Gst.PadProbeType.BUFFER:
            result = self._call(entry, "on_buffer", entry[2], pad, info.get_buffer())
        else:
            result = self._call(entry, "on_event", entry[2], pad, info.get_event())
        return _PROBE_RETURNS.get(result, Gst.PadProbeReturn.OK)

    def _call(self, entry, name, *args):
        function = entry[1].get(name)
        if not callable(function):
            return None
        try:
            return function(*args)
        except Exception:  # noqa: BLE001 - a failing script must not break the pipeline
            traceback.print_exc()
            return None

    def set_property(self, element_name, name, value):
        """Change a property, letting the element's scripts (on_property) take over first."""
        for entry in self._scripts:
            if entry[0]["target"][0] == "element" and entry[2].element is self.elements[element_name]:
                if self._call(entry, "on_property", entry[2], name, value):
                    return
        ScriptContext("", self.elements).set(element_name, name, value)

    def trigger(self, script_name, value=None):
        """What the Trigger button does in Pipelab: call on_trigger(ctx, value)."""
        for entry in self._scripts:
            if entry[0]["name"] == script_name:
                return self._call(entry, "on_trigger", entry[2], value)
        raise KeyError(script_name)
'''


def _code_literal(code: str) -> str:
    """Triple-quoted literal reproducing ``code`` exactly, one line per source line."""
    escaped = code.replace("\\", "\\\\").replace("'''", "\\'\\'\\'")
    return "'''\\\n" + escaped + ("" if escaped.endswith("\n") else "\\\n") + "'''"


def _target(graph: Graph, script: ProbeScript) -> tuple[str, str, str | None] | None:
    if script.target.kind == "node":
        node = graph.node(script.target.id)
        return ("element", node.name, None) if node else None
    edge = graph.edge(script.target.id)
    source = graph.node(edge.source) if edge else None
    return ("link", source.name, edge.source_pad) if source and edge else None


def enabled_scripts(graph: Graph) -> list[tuple[ProbeScript, tuple[str, str, str | None]]]:
    found = []
    for script in graph.scripts:
        target = _target(graph, script) if script.enabled else None
        if target is not None:
            found.append((script, target))
    return found


def scripts_table(graph: Graph) -> str:
    entries = []
    for script, target in enabled_scripts(graph):
        entries.append(
            "    {\n"
            f'        "name": {script.name!r},\n'
            f'        "target": {target!r},\n'
            f'        "code": {_code_literal(script.code)},\n'
            "    },"
        )
    return "\n\nPROBE_SCRIPTS = [\n" + "\n".join(entries) + "\n]\n"
