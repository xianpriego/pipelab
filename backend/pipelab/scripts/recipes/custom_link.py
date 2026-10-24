"""Custom probe on this link. Every callback is optional; see the help panel."""


def setup(ctx):
    ctx.state["buffers"] = 0


def on_buffer(ctx, pad, buffer):
    # buffer.pts / buffer.dts / buffer.duration are in ns; buffer.get_size(); ctx.is_keyframe(buffer)
    ctx.state["buffers"] += 1
    return PASS  # or DROP to drop it, REMOVE to remove this probe


def on_event(ctx, pad, event):
    return PASS


def on_trigger(ctx, value):
    ctx.log(f"{ctx.state['buffers']} buffers so far (trigger value {value!r})")
