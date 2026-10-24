"""Exports of graphs with components, slots, API functions and probe rules (docs/DYNAMIC.md §5)."""

import pytest

from pipelab.export import export_graph
from tests import export_dynamic_fixtures as fixtures
from tests.helpers import chain


def _export(catalog, program, fmt: str, name: str) -> str:
    graph, components = program()
    return export_graph(graph, catalog, fmt, name, components).content


def test_static_graphs_keep_the_simple_exports(catalog):
    graph = chain("videotestsrc", "fakesink")
    python = export_graph(graph, catalog, "python", "plain").content
    rust = export_graph(graph, catalog, "rust", "plain").content
    assert "class PlainPipeline" in python and "SlotManager" not in python
    assert "fn build_pipeline" in rust and "mod rt" not in rust


def test_python_component_builder_and_watchdog(catalog):
    code = _export(catalog, fixtures.watchdog_program, "python", "watchdog")
    compile(code, "watchdog.py", "exec")
    assert (
        "def build_test_source(name: str, host: ProbeHost | None = None, *, pattern: str | None = None, "
        "buffers: int | None = None) -> Gst.Bin:" in code
    )
    assert "buffers = 20 if buffers is None else buffers" in code
    assert "expose_port(container, elements['caps'], 'src', 'video', 'always')" in code
    assert "class TestSourceWatchdogWatchdogProbe(RuleSet):" in code
    assert "IDLE = (500,)" in code
    assert "self.post('branch-down', {'input': self.builtin('instance', ctx)" in code
    assert "f'{name}/watchdog'" in code  # $instance is the bin name
    assert "elements['cam'] = build_test_source('cam', host, **args_cam)" in code


def test_python_slot_and_function_api(catalog):
    slots = _export(catalog, fixtures.slot_program, "python", "slots")
    assert "INITIAL = {'tiles': [{'id': 'tile0', 'pattern': 'ball'}]}" in slots
    for method in ("def add_tile(self, *, pattern: str | None = None", "def remove_tile(", "def list_tiles("):
        assert method in slots
    assert "def restart_tile(self, instance_id: str) -> str:" in slots
    functions = _export(catalog, fixtures.function_program, "python", "functions")
    assert "def configure(self, pattern: str = 'ball') -> None:" in functions
    assert "self.set_element_property('src', 'pattern', pattern)" in functions
    assert "self._post('configured', {'pattern': pattern})" in functions


def test_python_kitchen_sink_compiles(catalog):
    code = _export(catalog, fixtures.kitchen_sink_program, "python", "kitchen")
    compile(code, "kitchen.py", "exec")
    assert "self.pipeline.set_property" not in code  # no sink-port slot: no message-forward
    assert "link_dynamic(elements, 'decode', 'src_%u', 'convert', 'sink')" in code
    sink = _export(catalog, fixtures.sink_slot_program, "python", "sink")
    assert 'self.pipeline.set_property("message-forward", True)' in sink


def test_rust_library_shape(catalog):
    code = _export(catalog, fixtures.slot_program, "rust", "slots")
    assert "pub struct TestTileParams {" in code and "pub pattern: Option<String>," in code
    assert (
        "pub fn build_test_tile(name: &str, params: &TestTileParams, host: &ProbeHost) -> Result<gst::Bin> {"
        in code
    )
    assert "pub struct Config {" in code and "pub tiles: Vec<TestTileParams>," in code
    assert "pub fn new(config: Config) -> Result<Self> {" in code
    for signature in (
        "pub fn add_tile(&self, params: TestTileParams) -> Result<String> {",
        "pub fn remove_tile(&self, id: &str) -> Result<()> {",
        "pub fn restart_tile(&self, id: &str) -> Result<String> {",
        "pub fn list_tiles(&self) -> Vec<(String, TestTileParams)> {",
        "pub fn connect_message<F: Fn(&rt::AppMessage) + Send + Sync + 'static>(&self, callback: F) {",
        "pub fn start(&self) -> Result<()> {",
        "pub fn stop(&self) -> Result<()> {",
        "pub fn send_eos(&self) {",
    ):
        assert signature in code
    assert code.index("// ---- Demo") < code.index("fn main() -> Result<()> {")


def test_rust_rules_are_explicit_code(catalog):
    code = _export(catalog, fixtures.watchdog_program, "rust", "watchdog")
    assert "impl rt::Rules for TestSourceWatchdogWatchdogRules {" in code
    assert "const IDLE: &'static [u64] = &[500];" in code
    assert "fn on_idle(&mut self, core: &Core, ctx: &Ctx, index: usize) {" in code
    assert 'core.post("branch-down", vec![("input", core.builtin("instance", ctx))' in code
    switch = _export(catalog, fixtures.keyframe_switch_program, "rust", "switch")
    assert "fn on_property(&mut self, core: &Core, ctx: &Ctx, property: &str) -> bool {" in switch
    assert 'if property == "active-pad" {' in switch
    assert 'rt::compare(&core.builtin("pad", ctx), "==", &self.vars.get("target"))' in switch
    functions = _export(catalog, fixtures.function_program, "rust", "functions")
    assert "pub fn configure(&self, pattern: &str) -> Result<()> {" in functions
    assert '"configure" => self.configure(&rt::arg(args, "pattern")' in functions


def test_rust_scripts_become_porting_notes(catalog):
    from pipelab.graph.models import ProbeScript, ScriptTarget

    graph, components = fixtures.watchdog_program()
    code = "def on_buffer(ctx):\n    return PASS\n"
    graph.scripts.append(
        ProbeScript(id="s1", name="count", code=code, target=ScriptTarget(kind="edge", id="e1"))
    )
    code = export_graph(graph, catalog, "rust", "watchdog", components).content
    assert "// --- count on the link leaving" in code


@pytest.mark.parametrize("fmt", ["gst-launch", "c"])
def test_static_formats_flatten_components(catalog, fmt):
    code = _export(catalog, fixtures.kitchen_sink_program, fmt, "kitchen")
    nested = "pattern=smpte" if fmt == "gst-launch" else '(G_OBJECT (cam_inner_src), "pattern", "smpte")'
    assert nested in code  # the instance parameter reaches the nested instance
    assert "Probe rule sets of components: watchdog (inner-src), quiet (wrapped)" in code
    assert "Pipeline API functions: everything, noop" in code


def test_gst_launch_slot_instances_get_free_request_pads(catalog):
    code = _export(catalog, fixtures.kitchen_sink_program, "gst-launch", "kitchen")
    assert "queue leaky=no ! mix.sink_0" in code  # the static link keeps sink_0
    assert "! mix.sink_1" in code  # the initial slot instance takes the next pad
    assert "sink_0::alpha=0.5 sink_1::alpha=0.8 sink_1::xpos=0 sink_1::ypos=10" in code
    watchdog = _export(catalog, fixtures.watchdog_program, "gst-launch", "watchdog")
    assert "videotestsrc is-live=true num-buffers=20 pattern=ball" in watchdog
