"""Open or close this link with the Trigger button; buffers are dropped while closed.

No element has to be added to the pipeline (unlike a valve), and with
WAIT_FOR_KEYFRAME the gate only reopens on a keyframe, requesting one upstream.
Trigger values: empty toggles, "open"/"close" (or true/false) set the state.
"""

WAIT_FOR_KEYFRAME = True


def setup(ctx):
    ctx.state.update(open=True, waiting=False)


def on_trigger(ctx, value):
    text = str(value or "").strip().lower()
    is_open = not ctx.state["open"] if not text else text in ("open", "true", "1", "on")
    ctx.state["open"] = is_open
    ctx.state["waiting"] = is_open and WAIT_FOR_KEYFRAME
    if ctx.state["waiting"]:
        ctx.request_keyframe()
    ctx.log("gate open" if is_open else "gate closed")


def on_buffer(ctx, pad, buffer):
    if not ctx.state["open"]:
        return DROP
    if ctx.state["waiting"]:
        if not ctx.is_keyframe(buffer):
            return DROP
        ctx.state["waiting"] = False
    return PASS
