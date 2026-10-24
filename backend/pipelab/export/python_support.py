"""Generic plumbing embedded in exported Python programs that use dynamic features.

It is plain library code (element helpers, slot management, rule-set wiring);
the rules themselves are generated as explicit methods by ``python_probes``.
"""

SUPPORT = '''

# --- Pipelab support ---------------------------------------------------------
PASS, DROP = "pass", "drop"
_FLUSH_EVENTS = ("flush-start", "flush-stop")


def launch_text(value: object) -> str:
    """A value as gst-launch / Gst.util_set_object_arg parse it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def configure(target: Gst.Object, typed: dict, parsed: dict) -> None:
    for key, value in typed.items():
        target.set_property(key, value)
    for key, value in parsed.items():
        Gst.util_set_object_arg(target, key, value)


def make_element(container: Gst.Bin, factory: str, name: str, typed: dict, parsed: dict) -> Gst.Element:
    element = Gst.ElementFactory.make(factory, name)
    if element is None:
        raise RuntimeError(f"element '{factory}' is not installed")
    configure(element, typed, parsed)
    container.add(element)
    return element


def pad_of(element: Gst.Element, name: str) -> tuple[Gst.Pad, bool]:
    """An existing pad, or a newly requested one; the flag tells if it was requested."""
    pad = element.get_static_pad(name)
    if pad is not None:
        return pad, False
    pad = element.request_pad_simple(name)
    if pad is None:
        raise RuntimeError(f"{element.get_name()} has no pad {name}")
    return pad, True


def link(elements: dict, src: str, src_pad: str, sink: str, sink_pad: str) -> None:
    source, _ = pad_of(elements[src], src_pad)
    target, _ = pad_of(elements[sink], sink_pad)
    if source.link(target) != Gst.PadLinkReturn.OK:
        raise RuntimeError(f"could not link {src}.{src_pad} to {sink}.{sink_pad}")


def matches(pad: Gst.Pad, name: str) -> bool:
    template = pad.get_pad_template()
    return pad.get_name() == name or (template is not None and template.name_template == name)


def link_dynamic(elements: dict, src: str, src_pad: str, sink: str, sink_pad: str) -> None:
    """Link a *sometimes* pad (name or template ``src_pad``) once it appears."""
    target, _ = pad_of(elements[sink], sink_pad)

    def on_pad_added(_element: Gst.Element, pad: Gst.Pad) -> None:
        if not matches(pad, src_pad) or target.is_linked():
            return
        if not pad.query_caps(None).can_intersect(target.query_caps(None)):
            return
        if pad.link(target) != Gst.PadLinkReturn.OK:
            print(f"could not link {src}.{pad.get_name()} to {sink}.{sink_pad}", file=sys.stderr)

    elements[src].connect("pad-added", on_pad_added)


def apply_value(element: Gst.Element, prop: str, value: object, pad: str | None = None) -> None:
    """Set a property like gst-launch; GstPad-typed properties take a pad name."""
    target = pad_of(element, pad)[0] if pad else element
    pspec = target.find_property(prop)
    if pspec is not None and pspec.value_type.is_a(Gst.Pad.__gtype__):
        target.set_property(prop, element.get_static_pad(str(value)))
    else:
        Gst.util_set_object_arg(target, prop, launch_text(value))


def expose_port(container: Gst.Bin, element: Gst.Element, pad: str, port: str, presence: str) -> None:
    """Ghost pad named ``port`` on ``container`` for an inner pad."""

    def ghost(inner: Gst.Pad) -> None:
        proxy = Gst.GhostPad.new(port, inner)
        if container.get_state(0)[1] != Gst.State.NULL:
            proxy.set_active(True)
        container.add_pad(proxy)

    if presence != "sometimes":
        ghost(pad_of(element, pad)[0])
        return

    def on_pad_added(_element: Gst.Element, inner: Gst.Pad) -> None:
        if matches(inner, pad) and container.get_static_pad(port) is None:
            ghost(inner)

    element.connect("pad-added", on_pad_added)


def _comparable(value: object) -> object:
    """Numbers (also numeric strings) compare as numbers, booleans as "true"/"false"."""
    if value is None or isinstance(value, bool):
        return None if value is None else launch_text(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def compare(left: object, op: str, right: object) -> bool:
    a, b = _comparable(left), _comparable(right)
    if op in ("==", "!="):
        return (a == b) == (op == "==")
    if not isinstance(a, float) or not isinstance(b, float):
        return False
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def structure(name: str, fields: dict) -> Gst.Structure:
    result = Gst.Structure.new_empty(name)
    for key, value in fields.items():
        if value is not None:
            result.set_value(key, value)
    return result


def make_event(kind: str, downstream: bool, name: str | None = None, fields: dict | None = None) -> list:
    if kind == "eos":
        return [Gst.Event.new_eos()]
    if kind == "flush":
        return [Gst.Event.new_flush_start(), Gst.Event.new_flush_stop(True)]
    if kind == "force-key-unit":
        if downstream:
            return [GstVideo.video_event_new_downstream_force_key_unit(
                Gst.CLOCK_TIME_NONE, Gst.CLOCK_TIME_NONE, Gst.CLOCK_TIME_NONE, True, 0)]
        return [GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE, True, 0)]
    custom = Gst.EventType.CUSTOM_DOWNSTREAM if downstream else Gst.EventType.CUSTOM_UPSTREAM
    return [Gst.Event.new_custom(custom, structure(name or "pipelab-event", fields or {}))]


def send_event(pad: Gst.Pad, events: list, downstream: bool) -> None:
    """Downstream events are pushed from src pads and sent into sink pads (and vice versa)."""
    is_src = pad.get_direction() == Gst.PadDirection.SRC
    for event in events:
        if downstream == is_src:
            pad.push_event(event)
        else:
            pad.send_event(event)


def send_to(element: Gst.Element, pad: str | None, events: list, downstream: bool) -> None:
    """Send events through a pad of ``element`` (by name), or to the element itself."""
    if pad:
        send_event(pad_of(element, str(pad))[0], events, downstream)
    else:
        for event in events:
            element.send_event(event)


def expand(text: str, values: dict) -> str:
    """Replace ``{name}`` placeholders (unknown ones are kept)."""
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text
'''
