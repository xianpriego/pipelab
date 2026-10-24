"""Ask the encoder upstream of this link for a keyframe every INTERVAL seconds.

Also on demand with the Trigger button. Handy to test how quickly receivers
recover, or to align key units with segment boundaries.
"""

INTERVAL = 2.0  # seconds of stream time


def on_buffer(ctx, pad, buffer):
    if buffer.pts == Gst.CLOCK_TIME_NONE:
        return PASS
    start = ctx.state.setdefault("start", buffer.pts)
    elapsed = (buffer.pts - start) / Gst.SECOND
    if elapsed >= ctx.state.get("next", INTERVAL):
        ctx.state["next"] = elapsed + INTERVAL
        ctx.request_keyframe()
    return PASS


def on_trigger(ctx, value):
    ctx.request_keyframe()
    ctx.log("keyframe requested")
