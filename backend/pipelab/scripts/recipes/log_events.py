"""Log every event crossing this link: caps changes, segments, tags, EOS, flushes…"""


def on_event(ctx, pad, event):
    name = Gst.EventType.get_name(event.type)
    structure = event.get_structure()
    detail = structure.to_string() if structure is not None else ""
    ctx.log(f"{name} {detail}"[:300])
    return PASS
