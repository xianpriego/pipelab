"""Generated Rust compiles without warnings and runs: plain pipelines and components.

Needs cargo: run with ``make test-rust`` (the ``rust-check`` service); skipped otherwise.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pipelab.export import export_graph
from tests.export_fixtures import components_program
from tests.helpers import chain
from tests.test_export_gst_launch import selector_graph

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not installed (make test-rust)"),
    pytest.mark.timeout(900),  # the first build compiles the gstreamer crates
]
SCENARIOS = Path(__file__).parent / "export_scenarios" / "rust"


def _cargo(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["cargo", *args], cwd=project, capture_output=True, text=True, timeout=850)


@pytest.fixture(scope="module")
def binaries(catalog, tmp_path_factory) -> Path:
    """One cargo project with one binary per exported program (plus the construct driver)."""
    project = tmp_path_factory.mktemp("rust-export")
    for name in ("Cargo.toml", "Cargo.lock"):
        shutil.copy(SCENARIOS / name, project / name)
    bins = project / "src" / "bin"
    bins.mkdir(parents=True)
    graph, components = components_program()
    library = export_graph(graph, catalog, "rust", "components", components).content
    (bins / "components.rs").write_text(library)
    construct = library.split("// ---- Demo")[0] + (SCENARIOS / "construct.rs").read_text()
    (bins / "construct.rs").write_text(construct)
    plain = chain(("videotestsrc", {"num-buffers": 5}), "fakesink")
    (bins / "plain.rs").write_text(export_graph(plain, catalog, "rust", "plain").content)
    (bins / "selector.rs").write_text(export_graph(selector_graph(), catalog, "rust", "selector").content)
    build = _cargo(project, "build", "--offline", "--bins")
    if build.returncode != 0 and "offline" in build.stderr:  # empty cache: download the crates once
        build = _cargo(project, "build", "--bins")
    assert build.returncode == 0, build.stderr
    warnings = [line for line in build.stderr.splitlines() if line.startswith("warning")]
    assert not warnings, build.stderr
    return Path(os.environ.get("CARGO_TARGET_DIR", project / "target")) / "debug"


def _run(binaries: Path, name: str) -> subprocess.CompletedProcess:
    result = subprocess.run([str(binaries / name)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "ERROR" not in result.stderr, result.stderr
    return result


def test_component_builders_create_the_bins(binaries):
    lines = _run(binaries, "construct").stdout.splitlines()
    assert lines == ["BUILT 5", "NESTED smpte", "BUFFERS 30", "PORTS true"]


def test_components_pipeline_runs_to_eos(binaries):
    _run(binaries, "components")


def test_plain_pipeline_runs_to_eos(binaries):
    _run(binaries, "plain")
