"""Generated Rust libraries compile without warnings and run the dynamic scenarios.

Needs cargo: run with ``make test-rust`` (the ``rust-check`` service); skipped otherwise.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pipelab.export import export_graph
from tests import export_dynamic_fixtures as fixtures
from tests.helpers import chain

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not installed (make test-rust)"),
    pytest.mark.timeout(900),  # the first build compiles the gstreamer crates
]
SCENARIOS = Path(__file__).parent / "export_scenarios" / "rust"
PROGRAMS = {
    "watchdog": (fixtures.watchdog_program, "watchdog"),
    "slots": (fixtures.slot_program, "slots"),
    "functions": (fixtures.function_program, "functions"),
    "switch": (fixtures.keyframe_switch_program, "switch"),
    "drain": (fixtures.sink_slot_program, "sink"),
    "construct": (fixtures.kitchen_sink_program, "kitchen"),
}


def _cargo(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["cargo", *args], cwd=project, capture_output=True, text=True, timeout=850)


@pytest.fixture(scope="module")
def binaries(catalog, tmp_path_factory) -> Path:
    """One cargo project, one binary per scenario: the generated library + the scenario's main."""
    project = tmp_path_factory.mktemp("rust-export")
    for name in ("Cargo.toml", "Cargo.lock"):
        shutil.copy(SCENARIOS / name, project / name)
    bins = project / "src" / "bin"
    bins.mkdir(parents=True)
    for scenario, (program, name) in PROGRAMS.items():
        graph, components = program()
        library = export_graph(graph, catalog, "rust", name, components).content.split("// ---- Demo")[0]
        (bins / f"{scenario}.rs").write_text(library + (SCENARIOS / f"{scenario}.rs").read_text())
    static = export_graph(chain(("videotestsrc", {"num-buffers": 5}), "fakesink"), catalog, "rust", "plain")
    (bins / "static.rs").write_text(static.content)
    build = _cargo(project, "build", "--offline", "--bins")
    if build.returncode != 0 and "offline" in build.stderr:  # empty cache: download the crates once
        build = _cargo(project, "build", "--bins")
    assert build.returncode == 0, build.stderr
    warnings = [line for line in build.stderr.splitlines() if line.startswith("warning")]
    assert not warnings, build.stderr
    return Path(os.environ.get("CARGO_TARGET_DIR", project / "target")) / "debug"


def _run(binaries: Path, scenario: str) -> list[list[str]]:
    result = subprocess.run([str(binaries / scenario)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "ERROR" not in result.stderr, result.stderr
    return [line.split() for line in result.stdout.splitlines()]


def _lines(output: list[list[str]], tag: str) -> list[list[str]]:
    return [words[1:] for words in output if words and words[0] == tag]


def test_watchdog_reports_the_stopped_instance(binaries):
    (name, instance, idle), *rest = _lines(_run(binaries, "watchdog"), "MESSAGE")
    assert not rest
    assert (name, instance) == ("branch-down", "input=cam")
    assert 500 <= int(idle.removeprefix("idle_ms=")) < 1500


def test_slot_instances_are_added_listed_and_removed(binaries):
    output = _run(binaries, "slots")
    assert _lines(output, "ADDED") == [["tile1", "tile2"]]
    assert _lines(output, "LIST") == [["tile0,tile1,tile2"], ["tile0,tile2"]]
    assert _lines(output, "RESTART") == [["tile2"]]
    assert _lines(output, "FINAL") == [["tile0,tile2", "Playing"]]
    pads = _lines(output, "PADS")[0][0].split(",")
    assert len(pads) == 2 and "sink_1" not in pads


def test_api_function_sets_a_property_and_posts_a_message(binaries):
    output = _run(binaries, "functions")
    assert _lines(output, "PATTERN") == [["snow"]]
    assert _lines(output, "MESSAGE") == [["configured", "pattern=snow", 'source=Some("functions")']]


def test_keyframe_gated_switch(binaries):
    output = _run(binaries, "switch")
    assert _lines(output, "INTERCEPTED") == [["true"]]
    assert _lines(output, "ACTIVE") == [["sink_0"], ["sink_1"]]
    assert _lines(output, "MESSAGE")[0] == ["switched", "pad=sink_1"]


def test_sink_instances_drain_before_removal(binaries):
    output = _run(binaries, "drain")
    assert _lines(output, "STATE") == [["output0,output1", "pads=src_0,src_1"], ["output1", "pads=src_1"]]


def test_kitchen_sink_builds(binaries):
    output = _run(binaries, "construct")
    assert _lines(output, "BUILT") == [["8", "1"]]
    assert _lines(output, "NESTED") == [["smpte"]]


def test_static_export_runs(binaries):
    subprocess.run([str(binaries / "static")], check=True, capture_output=True, timeout=60)
