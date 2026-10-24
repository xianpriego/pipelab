"""Probe scripts in exported code."""

import shutil
import subprocess
import sys
import textwrap

import pytest

from pipelab.export import export_graph
from pipelab.graph.models import ProbeScript, ScriptTarget
from pipelab.importer import import_gst_launch
from pipelab.scripts.catalog import recipes

SELECTOR = (
    "input-selector name=sel ! fakesink "
    "videotestsrc is-live=true ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_0 "
    "videotestsrc is-live=true pattern=ball ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_1"
)
DRIVER = textwrap.dedent(
    """
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("exported", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.Gst.init(None)
    pipeline = module.SelectorPipeline()
    pipeline.loop = module.GLib.MainLoop()
    pipeline.start()
    module.GLib.timeout_add(1000, lambda: pipeline.set_property("sel", "active-pad", "sink_1") and False)
    module.GLib.timeout_add(4000, lambda: pipeline.loop.quit() and False)
    pipeline.loop.run()
    print("ACTIVE", pipeline.elements["sel"].get_property("active-pad").get_name())
    pipeline.stop()
    """
)


@pytest.fixture
def graph(catalog):
    imported = import_gst_launch(SELECTOR, catalog).graph
    selector = next(n for n in imported.nodes if n.factory == "input-selector")
    recipe = next(r for r in recipes() if r.id == "keyframe-switch")
    imported.scripts = [
        ProbeScript(
            id="s1", name=recipe.name, target=ScriptTarget(kind="node", id=selector.id), code=recipe.code
        )
    ]
    return imported


def test_python_export_runs_the_scripts(graph, catalog, tmp_path):
    program = tmp_path / "selector.py"
    program.write_text(export_graph(graph, catalog, "python", "selector").content)
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    run = subprocess.run(
        [sys.executable, str(driver), str(program)], capture_output=True, text=True, timeout=60
    )
    assert "ACTIVE sink_1" in run.stdout, run.stderr[-2000:]
    assert "switched to sink_1 on a keyframe" in run.stderr


def test_other_exports_carry_porting_notes(graph, catalog):
    for language, marker in (
        ("c", " * --- Switch on keyframe"),
        ("rust", "// --- Switch on keyframe"),
        ("gst-launch", "# --- Switch on keyframe"),
    ):
        content = export_graph(graph, catalog, language, "selector").content
        assert marker in content and "def on_buffer(ctx, pad, buffer):" in content


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")
def test_c_export_with_notes_still_compiles(graph, catalog, tmp_path):
    source = tmp_path / "selector.c"
    source.write_text(export_graph(graph, catalog, "c", "selector").content)
    flags = subprocess.run(
        ["pkg-config", "--cflags", "--libs", "gstreamer-1.0"], capture_output=True, text=True, check=True
    ).stdout.split()
    subprocess.run(["gcc", str(source), "-o", str(tmp_path / "selector"), *flags], check=True, timeout=120)
