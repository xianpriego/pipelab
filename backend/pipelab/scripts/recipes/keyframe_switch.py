"""Switch input-selector / output-selector only on a keyframe.

Changing active-pad from the UI (the radio on the node) does not switch at
once: the request waits for the next keyframe, so whatever is downstream
(decoder, muxer, network) never starts on a delta frame. A keyframe is also
requested from the encoder upstream so the switch happens quickly.
"""

REQUEST_KEYFRAME = True  # ask the encoder of the new input for a key unit


def on_property(ctx, name, value):
    if name != "active-pad":
        return False  # other properties are applied normally
    ctx.state["target"] = value
    if REQUEST_KEYFRAME:
        input_pad = value if _is_input_selector(ctx) else "sink"
        ctx.request_keyframe(ctx.pad_named(input_pad))
    ctx.log(f"switch to {value} requested, waiting for a keyframe")
    return True  # handled: do not switch yet


def on_buffer(ctx, pad, buffer):
    target = ctx.state.get("target")
    if target is None or not ctx.is_keyframe(buffer):
        return PASS
    if _is_input_selector(ctx) and pad.get_name() != target:
        return PASS  # keyframe of another input
    ctx.state["target"] = None
    ctx.element.set_property("active-pad", ctx.pad_named(target))
    ctx.log(f"switched to {target} on a keyframe", pts=buffer.pts / Gst.SECOND)
    return PASS


def _is_input_selector(ctx):
    return ctx.element.get_factory().get_name() == "input-selector"
