"""Generated Python libraries run the dynamic scenarios of docs/DYNAMIC.md."""

import subprocess
import sys
from pathlib import Path

import pytest

from pipelab.export import export_graph
from tests import export_dynamic_fixtures as fixtures

pytestmark = pytest.mark.runtime
DRIVERS = Path(__file__).parent / "export_scenarios" / "python"


def _run(catalog, tmp_path, program, name: str, driver: str) -> list[list[str]]:
    """Export ``program``, run the driver on it and return its output lines as words."""
    graph, components = program()
    module = tmp_path / f"{name}.py"
    module.write_text(export_graph(graph, catalog, "python", name, components).content)
    result = subprocess.run(
        [sys.executable, str(DRIVERS / driver), str(module)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert "ERROR" not in result.stderr, result.stderr
    return [line.split() for line in result.stdout.splitlines()]


def _lines(output: list[list[str]], tag: str) -> list[list[str]]:
    return [words[1:] for words in output if words and words[0] == tag]


def test_watchdog_reports_the_stopped_instance(catalog, tmp_path):
    output = _run(catalog, tmp_path, fixtures.watchdog_program, "watchdog", "watchdog.py")
    messages = _lines(output, "MESSAGE")
    assert len(messages) == 1
    name, instance, idle_ms = messages[0]
    assert (name, instance) == ("branch-down", "cam")
    assert 500 <= int(idle_ms) < 1500


def test_slot_instances_are_added_listed_and_removed(catalog, tmp_path):
    output = _run(catalog, tmp_path, fixtures.slot_program, "slots", "slots.py")
    assert _lines(output, "ADDED") == [["tile1", "tile2"]]
    assert _lines(output, "LIST") == [["tile0,tile1,tile2"], ["tile0,tile2"]]
    assert _lines(output, "RESTART") == [["tile2"]]
    assert _lines(output, "FINAL") == [["tile0,tile2", "playing"]]
    pads = _lines(output, "PADS")[0][0].split(",")
    assert len(pads) == 2 and "sink_1" not in pads  # the removed instance released its pad
    assert _lines(output, "EXIT") == [["0"]]


def test_api_function_sets_a_property_and_posts_a_message(catalog, tmp_path):
    output = _run(catalog, tmp_path, fixtures.function_program, "functions", "functions.py")
    assert _lines(output, "PATTERN") == [["snow"]]
    assert _lines(output, "MESSAGE") == [["configured", "snow", "functions"]]


def test_keyframe_gated_switch(catalog, tmp_path):
    output = _run(catalog, tmp_path, fixtures.keyframe_switch_program, "switch", "switch.py")
    assert _lines(output, "INTERCEPTED") == [["True"]]
    assert _lines(output, "ACTIVE") == [["sink_0"], ["sink_1"]]  # applied later, on a keyframe
    (name, pad, delay), *_ = _lines(output, "MESSAGE")
    assert (name, pad) == ("switched", "sink_1")
    assert float(delay) < 2


def test_sink_instances_drain_before_removal(catalog, tmp_path):
    output = _run(catalog, tmp_path, fixtures.sink_slot_program, "sink", "drain.py")
    assert _lines(output, "ADDED") == [["output1"]]
    assert _lines(output, "STATE") == [["output0,output1", "pads=src_0,src_1"], ["output1", "pads=src_1"]]


def test_kitchen_sink_builds(catalog, tmp_path):
    output = _run(catalog, tmp_path, fixtures.kitchen_sink_program, "kitchen", "construct.py")
    assert _lines(output, "BUILT") == [["8", "1"]]
    assert _lines(output, "NESTED") == [["smpte"]]
