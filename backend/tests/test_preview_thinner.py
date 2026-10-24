import random

from pipelab.gst import Gst
from pipelab.runtime.worker.encoder import FrameThinner

FRAME_30 = Gst.SECOND // 30


def _kept(timestamps, max_fps=15):
    thinner = FrameThinner(max_fps)
    return sum(thinner.keep(pts) for pts in timestamps)


def test_halves_a_30fps_stream_even_with_jitter():
    rng = random.Random(1)
    timestamps = [i * FRAME_30 + rng.randint(-3_000_000, 3_000_000) for i in range(300)]
    assert 145 <= _kept(timestamps) <= 155


def test_keeps_slower_streams_untouched():
    assert _kept([i * Gst.SECOND // 10 for i in range(50)]) == 50


def test_recovers_after_timestamps_jump_back():
    timestamps = [i * FRAME_30 for i in range(30)] + [i * FRAME_30 for i in range(30)]
    assert _kept(timestamps) >= 28
