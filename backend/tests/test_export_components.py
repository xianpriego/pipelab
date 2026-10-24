"""Exports of graphs with components: Python/Rust builders, flattened gst-launch and C."""

import subprocess
import sys
from pathlib import Path

import pytest

from pipelab.export import export_graph
from tests.export_fixtures import components_program

DRIVERS = Path(__file__).parent / "export_scenarios" / "python"


def _export(catalog, fmt: str) -> str:
    graph, components = components_program()
    return export_graph(graph, catalog, fmt, "components", components).content


def test_python_builders_and_pipeline_class(catalog):
    code = _export(catalog, "python")
    compile(code, "components.py", "exec")
    assert (
        "def build_inner_src(name: str, *, pattern: str | None = None, buffers: int | None = None, "
        "live: bool | None = None) -> Gst.Bin:" in code
    )
    assert "buffers = 30 if buffers is None else buffers" in code
    assert "    args_inner['pattern'] = pattern" in code  # wrapped forwards to the nested instance
    assert "expose_port(container, elements['decode'], 'src_%u', 'video', 'sometimes')" in code
    assert "link_dynamic(elements, 'dec', 'video', 'convert', 'sink')" in code
    assert "configure(pad_of(elements['mix'], 'sink_1')[0], {'xpos': 160}, {})" in code
    assert "class ComponentsPipeline:" in code
    assert code.index("def build_inner_src") < code.index("def build_wrapped")  # dependencies first


def test_rust_builders_and_pipeline_type(catalog):
    code = _export(catalog, "rust")
    assert "pub struct InnerSrcParams {" in code and "pub buffers: Option<i64>," in code
    assert "pub fn build_inner_src(name: &str, params: &InnerSrcParams) -> Result<gst::Bin> {" in code
    assert "let buffers = params.buffers.clone().or(Some(30));" in code
    assert 'rt::expose_port(&container, &elements["decode"], "src_%u", "video", "sometimes")?;' in code
    assert 'rt::link_dynamic(&elements, "dec", "video", "convert", "sink")?;' in code
    for signature in (
        "pub fn new() -> Result<Self> {",
        "pub fn start(&self) -> Result<()> {",
        "pub fn stop(&self) -> Result<()> {",
        "pub fn send_eos(&self) {",
        "pub fn connect_message<F: Fn(&gst::Message) + Send + Sync + 'static>(&self, callback: F) {",
        "pub fn element(&self, path: &str) -> Result<gst::Element> {",
    ):
        assert signature in code
    assert code.count("{") == code.count("}")


def test_static_formats_expand_instances(catalog):
    launch = _export(catalog, "gst-launch")
    assert "component:" not in launch
    # Parameters (instance value, nested value, defaults) become plain properties.
    assert "videotestsrc is-live=false num-buffers=30 pattern=smpte" in launch
    assert "decodebin ! videoconvert ! mix.sink_1" in launch
    c = _export(catalog, "c")
    assert "component:" not in c and "cam_inner_src" in c and "dec_decode" in c


@pytest.mark.runtime
def test_python_export_builds_and_runs(catalog, tmp_path):
    module = tmp_path / "components.py"
    module.write_text(_export(catalog, "python"))
    built = subprocess.run(
        [sys.executable, str(DRIVERS / "construct.py"), str(module)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert built.returncode == 0, built.stderr
    assert built.stdout.split("\n")[:4] == ["BUILT 5", "NESTED smpte", "BUFFERS 30", "PORTS True"]
    played = subprocess.run([sys.executable, str(module)], capture_output=True, text=True, timeout=60)
    assert played.returncode == 0 and "ERROR" not in played.stderr, played.stderr
