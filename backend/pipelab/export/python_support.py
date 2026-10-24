"""Generic helpers embedded in exported Python programs (elements, links, ghost pads)."""

SUPPORT = '''

# --- Pipelab helpers ---------------------------------------------------------
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
'''
