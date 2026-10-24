"""Custom script on this element. It probes the element's sink pads
(WATCH = "src" or "all" to change that); every callback is optional."""

WATCH = "sink"


def setup(ctx):
    ctx.log(f"attached to {ctx.element.get_name()}")


def on_buffer(ctx, pad, buffer):
    return PASS


def on_property(ctx, name, value):
    return False  # True = handled here instead of setting the property now


def on_trigger(ctx, value):
    ctx.log(f"triggered with {value!r}")
