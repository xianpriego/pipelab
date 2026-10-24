"""NVIDIA elements: the image must expose the complete nvcodec set when a GPU is visible.

Run with a GPU through ``make test GPU=1``; without one the GPU checks are skipped.
"""

import os
from pathlib import Path

import pytest

from tests.api_client import api_client
from tests.helpers import chain
from tests.helpers import graph as graph_of
from tests.runtime_helpers import create_project, events_until, is_stopped

CUDA_FILTERS = ("cudaconvert", "cudascale", "cudaconvertscale", "cudacompositor")
CUDA_SMALL = "video/x-raw(memory:CUDAMemory),width=320,height=240"


@pytest.fixture(scope="module")
def gpu(catalog):
    if "nvh264enc" not in catalog:
        pytest.skip("no NVIDIA GPU visible to the container")
    return catalog


@pytest.fixture(scope="module")
def client(gpu, data_dir):
    with api_client(data_dir) as client:
        yield client


def test_image_ships_the_cuda_runtime_compiler():
    assert Path(os.environ["GST_CUDA_NVRTC_LIBNAME"]).is_file()


def test_cuda_filters_are_registered_with_a_gpu(gpu):
    assert [name for name in CUDA_FILTERS if name not in gpu] == []


def _run_to_eos(client, graph):
    project_id = create_project(client, graph)
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={})
        events, _ = events_until(ws, is_stopped, timeout=60)
    assert [e["text"] for e in events if e["type"] == "bus" and e["kind"] == "error"] == []
    assert any(e["type"] == "bus" and e["kind"] == "eos" for e in events)


@pytest.mark.runtime
def test_frames_stay_on_the_gpu_through_scale_encode_and_decode(client):
    _run_to_eos(
        client,
        chain(
            ("videotestsrc", {"num-buffers": 60}),
            "cudaupload",
            "cudaconvertscale",
            ("capsfilter", {"caps": CUDA_SMALL}),
            "nvh264enc",
            "h264parse",
            "nvh264dec",
            "cudadownload",
            "fakesink",
        ),
    )


@pytest.mark.runtime
def test_cuda_compositor_mixes_two_sources(client):
    _run_to_eos(
        client,
        graph_of(
            [
                ("a", "videotestsrc", {"num-buffers": 60}),
                ("ua", "cudaupload"),
                ("b", "videotestsrc", {"num-buffers": 60, "pattern": "ball"}),
                ("ub", "cudaupload"),
                ("mix", "cudacompositor"),
                ("enc", "nvh265enc"),
                ("out", "fakesink"),
            ],
            [
                ("a", "src", "ua", "sink"),
                ("ua", "src", "mix", "sink_%u"),
                ("b", "src", "ub", "sink"),
                ("ub", "src", "mix", "sink_%u"),
                ("mix", "src", "enc", "sink"),
                ("enc", "src", "out", "sink"),
            ],
        ),
    )
