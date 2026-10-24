"""Drop delta frames until the first keyframe.

Useful when joining a live stream mid-GOP: decoders and muxers downstream only
see a clean stream that starts on a key unit. After a flush (seek) it waits
again.
"""


def on_buffer(ctx, pad, buffer):
    if ctx.state.get("synced"):
        return PASS
    if ctx.is_keyframe(buffer):
        ctx.state["synced"] = True
        ctx.log(f"first keyframe after {ctx.state.get('dropped', 0)} dropped buffers")
        return PASS
    ctx.state["dropped"] = ctx.state.get("dropped", 0) + 1
    return DROP


def on_event(ctx, pad, event):
    if event.type == Gst.EventType.FLUSH_STOP:
        ctx.state["synced"] = False
    return PASS
