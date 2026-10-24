"""Send EOS downstream after DURATION seconds of stream time on this link.

Finalises recordings (mp4mux, splitmuxsink…) after a fixed length while the
rest of the pipeline keeps running.
"""

DURATION = 10.0  # seconds


def on_buffer(ctx, pad, buffer):
    if ctx.state.get("done"):
        return DROP
    if buffer.pts == Gst.CLOCK_TIME_NONE:
        return PASS
    start = ctx.state.setdefault("start", buffer.pts)
    if (buffer.pts - start) / Gst.SECOND >= DURATION:
        ctx.state["done"] = True
        pad.push_event(Gst.Event.new_eos())
        ctx.log(f"EOS sent after {DURATION} s")
        return DROP
    return PASS
