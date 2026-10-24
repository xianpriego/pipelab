"""Small building blocks hardened after the code review: values, names, files, legacy documents."""

import pytest

from pipelab.catalog.service import CatalogService
from pipelab.graph.editing import default_name, unique_name
from pipelab.graph.models import Graph
from pipelab.gst.values import parse_bool, parse_number
from pipelab.storage.files import atomic_write
from tests.helpers import chain


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), ("off", False), ("NO", False), ("0", False), ("on", True), ("yes", True), (1, True)],
)
def test_parse_bool_reads_booleans_like_gstreamer(value, expected):
    assert parse_bool(value) is expected


def test_parse_bool_falls_back_to_the_default():
    assert parse_bool(None, default=True) is True
    assert parse_bool("maybe", default=False) is False


def test_parse_number_handles_hex_leading_zeros_and_rejects_text():
    assert parse_number("0x10", integer=True) == 16
    assert parse_number("08", integer=True) == 8
    assert parse_number("1.5", integer=False) == 1.5
    assert parse_number("1.5", integer=True) is None
    assert parse_number("fast", integer=False) is None
    assert parse_number(True, integer=True) is None


def test_default_names_keep_digits_that_belong_to_the_factory():
    assert default_name("queue", {"queue0"}) == "queue1"
    assert default_name("avdec_h264", set()) == "avdec_h264-0"
    graph = chain("avdec_h264", "fakesink")
    graph.nodes[0].name = "avdec_h264-0"
    assert unique_name(graph, "avdec_h264") == "avdec_h264-1"


def test_atomic_write_replaces_without_leftovers(tmp_path):
    target = tmp_path / "doc.json"
    atomic_write(target, "one")
    atomic_write(target, "two")
    assert target.read_text() == "two"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["doc.json"]


def test_unreadable_catalog_cache_is_discarded_for_a_rebuild(tmp_path):
    cache = tmp_path / "catalog-x.json"
    cache.write_text('{"elements": [')  # a write interrupted by a crash
    assert CatalogService._cached(cache) is None
    assert not cache.exists()


def test_documents_saved_by_older_versions_still_load():
    legacy = {
        "nodes": [{"id": "n0", "factory": "fakesink", "name": "sink"}],
        "edges": [],
        "scripts": [{"id": "s1", "target": {"kind": "node", "id": "n0"}, "code": ""}],
        "probes": [],
        "slots": [],
        "functions": [],
    }
    graph = Graph.model_validate(legacy)
    assert [n.name for n in graph.nodes] == ["sink"]
    assert "scripts" not in graph.model_dump()
