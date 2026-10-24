"""Warn when no buffer crosses this link for more than MAX_GAP seconds."""

import time

MAX_GAP = 0.5  # seconds


def setup(ctx):
    ctx.state.update(last=None, stalled=False)
    GLib.timeout_add(max(int(MAX_GAP * 500), 50), _check, ctx)


def _check(ctx):
    last = ctx.state["last"]
    if last is not None and not ctx.state["stalled"] and time.monotonic() - last > MAX_GAP:
        ctx.state["stalled"] = True
        ctx.log(f"stalled: no buffer for more than {MAX_GAP} s", level="warning")
    return True  # keep the timer running


def on_buffer(ctx, pad, buffer):
    now = time.monotonic()
    if ctx.state["stalled"]:
        ctx.state["stalled"] = False
        ctx.log(f"flowing again after {now - ctx.state['last']:.2f} s")
    ctx.state["last"] = now
    return PASS
