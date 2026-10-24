"""Simulate packet loss on this link to test how the receiver copes.

Trigger with a number to change the loss percentage while running.
"""

import random

LOSS_PERCENT = 5.0  # probability of starting a loss burst, per buffer
BURST = 1  # consecutive buffers lost each time


def on_buffer(ctx, pad, buffer):
    left = ctx.state.get("burst", 0)
    if left:
        ctx.state["burst"] = left - 1
        return DROP
    if random.random() * 100 < LOSS_PERCENT:
        ctx.state["burst"] = BURST - 1
        ctx.state["lost"] = ctx.state.get("lost", 0) + BURST
        return DROP
    return PASS


def on_trigger(ctx, value):
    global LOSS_PERCENT
    LOSS_PERCENT = float(value or 0)
    ctx.log(f"loss set to {LOSS_PERCENT}% ({ctx.state.get('lost', 0)} buffers lost so far)")
