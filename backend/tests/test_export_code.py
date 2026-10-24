"""Python, C, Rust and JSON exporters plus the format registry."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from pipelab.export import FORMATS, export_graph
from pipelab.export.common import build_spec, identifier
from pipelab.graph.models import Graph
from tests.helpers import chain, graph
from tests.test_export_gst_launch import compositor_graph, demuxer_graph, selector_graph, tee_graph

RUNNABLE = chain(("videotestsrc", {"num-buffers": 30, "pattern": "ball"}), "videoconvert", "fakesink")


def test_registry_lists_every_format(catalog):
    assert [f.id for f in FORMATS] == ["gst-launch", "python", "c", "rust", "json"]
    with pytest.raises(KeyError):
        export_graph(RUNNABLE, catalog, "cobol")


@pytest.mark.parametrize(
    ("format_id", "filename", "language"),
    [
        ("gst-launch", "my_pipe.sh", "bash"),
        ("python", "my_pipe.py", "python"),
        ("c", "my_pipe.c", "c"),
        ("rust", "main.rs", "rust"),
        ("json", "my_pipe.pipelab.json", "json"),
    ],
)
def test_export_result_metadata(catalog, format_id, filename, language):
    result = export_graph(RUNNABLE, catalog, format_id, "My pipe")
    assert (result.format, result.filename, result.language) == (format_id, filename, language)
    assert result.content == export_graph(RUNNABLE, catalog, format_id, "My pipe").content


def test_identifiers_are_sanitized():
    assert identifier("video-src.1") == "video_src_1"
    assert identifier("1st") == "e_1st"
    assert identifier("class") == "class_"
    assert identifier("pad", frozenset({"pad"})) == "pad_"


def test_spec_classifies_properties_and_links(catalog):
    spec = build_spec(selector_graph(), catalog, "p")
    selector = next(e for e in spec.elements if e.name == "sel")
    assert [p.name for p in selector.pad_refs] == ["active-pad"]
    demux = build_spec(demuxer_graph(), catalog, "p")
    assert [(link.source_pad, link.dynamic) for link in demux.dynamic_links] == [
        ("video_%u", True),
        ("audio_%u", True),
    ]


@pytest.mark.parametrize(
    "built", [RUNNABLE, tee_graph(), demuxer_graph(), compositor_graph(), selector_graph()]
)
def test_python_export_compiles(catalog, built):
    compile(export_graph(built, catalog, "python", "test").content, "pipeline.py", "exec")


def test_python_export_uses_typed_and_parsed_setters(catalog):
    content = export_graph(compositor_graph(), catalog, "python", "Picture in picture").content
    assert "class PictureInPicturePipeline:" in content
    assert "elements['b'] = make_element(container, 'videotestsrc', 'b', {}, {'pattern': 'ball'})" in content
    assert "configure(pad_of(elements['c'], 'sink_1')[0], {'alpha': 0.5, 'xpos': 320}, {})" in content
    selector = export_graph(selector_graph(), catalog, "python", "s").content
    assert "apply_value(elements['sel'], 'active-pad', 'sink_1')" in selector
    demux = export_graph(demuxer_graph(), catalog, "python", "d").content
    assert "link_dynamic(elements, 'd', 'video_%u', 'qv', 'sink')" in demux


@pytest.mark.runtime
def test_python_export_runs_until_eos(catalog, tmp_path):
    script = tmp_path / "pipeline.py"
    script.write_text(export_graph(RUNNABLE, catalog, "python", "runnable").content)
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


@pytest.mark.runtime
@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
@pytest.mark.parametrize("built", [RUNNABLE, compositor_graph(), selector_graph(), demuxer_graph()])
def test_c_export_compiles(catalog, tmp_path, built):
    source = tmp_path / "pipeline.c"
    source.write_text(export_graph(built, catalog, "c", "test").content)
    command = (
        f"gcc -Wall -Werror {source} -o {tmp_path / 'pipeline'} $(pkg-config --cflags --libs gstreamer-1.0)"
    )
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr


@pytest.mark.runtime
@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_c_export_runs_until_eos(catalog, tmp_path):
    source = tmp_path / "pipeline.c"
    source.write_text(export_graph(RUNNABLE, catalog, "c", "runnable").content)
    binary = tmp_path / "pipeline"
    subprocess.run(
        f"gcc {source} -o {binary} $(pkg-config --cflags --libs gstreamer-1.0)",
        shell=True,
        check=True,
        timeout=120,
    )
    assert subprocess.run([str(binary)], capture_output=True, timeout=60).returncode == 0


def test_c_export_avoids_reserved_names(catalog):
    built = graph(
        [("int", "videotestsrc"), ("video-sink.1", "fakesink")], [("int", "src", "video-sink.1", "sink")]
    )
    content = export_graph(built, catalog, "c", "names").content
    assert "GstElement *int_;" in content
    assert 'link_pads (int_, "src", video_sink_1, "sink")' in content


def test_rust_export_structure(catalog):
    content = export_graph(compositor_graph(), catalog, "rust", "comp").content
    assert '//!   gstreamer = "0.25"' in content
    make = 'rt::make_element(&container, "videotestsrc", "b", &[("pattern", "ball")])?'
    assert f'elements.insert("b".into(), {make});' in content
    assert 'rt::link(&elements, "a", "src", "c", "sink_0")?;' in content
    assert 'rt::configure_pad(&elements["c"], "sink_1", &[("alpha", "0.5"), ("xpos", "320")])?;' in content
    assert content.count("{") == content.count("}")
    demux = export_graph(demuxer_graph(), catalog, "rust", "demux").content
    assert 'rt::link_dynamic(&elements, "d", "video_%u", "qv", "sink")?;' in demux
    selector = export_graph(selector_graph(), catalog, "rust", "sel").content
    assert 'rt::apply_value(&elements["sel"], "active-pad", "sink_1", None)?;' in selector


def test_json_document_round_trips(catalog):
    document = json.loads(export_graph(compositor_graph(), catalog, "json", "comp").content)
    assert document["format"] == "pipelab/graph@1"
    assert document["name"] == "comp"
    assert Graph.model_validate(document["graph"]) == compositor_graph()
