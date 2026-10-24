"""Component library: CRUD, catalog overlay, grouping/expanding and validation."""

import pytest

from pipelab.components.grouping import expand_instance, group_into_component
from pipelab.components.overlay import overlay_catalog
from pipelab.components.validate import validate_component
from pipelab.graph.analyzer import Analyzer
from pipelab.graph.validate import validate_graph
from tests.api_client import api_client
from tests.dynamic_fixtures import mixer_with_slot, source_component
from tests.helpers import chain


@pytest.fixture(scope="module")
def client(catalog, tmp_path_factory):
    with api_client(tmp_path_factory.mktemp("components")) as client:
        yield client


@pytest.fixture(scope="module")
def library_analyzer(catalog):
    components = {"test-source": source_component()}
    return Analyzer(overlay_catalog(catalog, components), components)


def test_crud_and_catalog_overlay(client):
    component = source_component().model_dump(mode="json")
    saved = client.put("/api/components/test-source", json=component).json()
    assert saved["version"] == 1
    assert client.put("/api/components/test-source", json=component).json()["version"] == 2
    assert [c["id"] for c in client.get("/api/components").json()] == ["test-source"]
    virtual = client.get("/api/catalog/component:test-source").json()
    assert virtual["family"] == "component" and "source" in virtual["categories"]
    assert (
        virtual["pad_templates"][0]["name"] == "src"
        and "width=(int)320" in virtual["pad_templates"][0]["caps"]
    )
    assert virtual["properties"][0]["name"] == "pattern" and virtual["properties"][0]["type"] == "enum"
    assert client.put("/api/components/Bad Id", json={**component, "id": "Bad Id"}).status_code == 422


def test_instances_validate_like_elements(library_analyzer):
    graph = chain(("component:test-source", {"pattern": "ball"}), "videoconvert", "fakesink")
    assert [i for i in validate_graph(library_analyzer, graph) if i.severity == "error"] == []
    wrong = chain("component:test-source", "audioconvert", "fakesink")
    assert any(i.rule == "caps-incompatible" for i in validate_graph(library_analyzer, wrong))
    missing = chain("component:nope", "fakesink")
    assert any("not in the library" in i.message for i in validate_graph(library_analyzer, missing))


def test_slots_count_as_sources(library_analyzer):
    issues = validate_graph(library_analyzer, mixer_with_slot())
    assert [i.message for i in issues if i.severity == "error"] == []
    broken = mixer_with_slot()
    broken.slots[0].links[0].pad = "nope_%u"
    assert any(i.rule == "slot" for i in validate_graph(library_analyzer, broken))


def test_component_validation_accepts_exposed_pads(library_analyzer):
    component = source_component()
    assert validate_component(library_analyzer, component) == []
    component.ports[0].pad = "sink"
    assert any(i.rule == "component" for i in validate_component(library_analyzer, component))


def test_validate_endpoint_takes_the_draft(client):
    draft = source_component().model_dump(mode="json")
    draft["ports"][0]["pad"] = "sink"
    answer = client.post("/api/components/validate", json={"component": draft})
    assert answer.status_code == 200, answer.text
    assert any(i["rule"] == "component" for i in answer.json()["issues"])


def test_group_and_expand_round_trip(library_analyzer):
    graph = chain(("videotestsrc", {"pattern": "ball"}), "videoconvert", "videoscale", "fakesink")
    component, grouped = group_into_component(graph, ["n1", "n2"], "convert-scale", "Convert + scale")
    assert [p.name for p in component.ports] == ["sink", "src"]
    assert sorted(n.factory for n in grouped.nodes) == ["component:convert-scale", "fakesink", "videotestsrc"]
    instance = next(n for n in grouped.nodes if n.factory.startswith("component:"))
    assert {(e.source_pad, e.target_pad) for e in grouped.edges} == {("src", "sink")}
    expanded = expand_instance(grouped, instance.id, component)
    assert sorted(n.factory for n in expanded.nodes) == [
        "fakesink",
        "videoconvert",
        "videoscale",
        "videotestsrc",
    ]
    assert len(expanded.edges) == 3


def test_from_selection_endpoint(client):
    graph = chain("videotestsrc", "videoconvert", "fakesink").model_dump()
    created = client.post(
        "/api/components/from-selection",
        json={"graph": graph, "node_ids": ["n1"], "id": "just-convert", "name": "Convert"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["component"]["version"] == 1
    assert any(n["factory"] == "component:just-convert" for n in body["graph"]["nodes"])
    again = client.post(
        "/api/components/from-selection",
        json={"graph": graph, "node_ids": ["n1"], "id": "just-convert", "name": "Convert"},
    )
    assert again.status_code == 409


def test_usage_lists_dependants_before_deleting(client):
    client.put("/api/components/test-source", json=source_component().model_dump(mode="json"))
    graph = mixer_with_slot().model_dump()
    project = client.post("/api/projects", json={"name": "uses it", "graph": graph}).json()
    usage = client.get("/api/components/test-source/usage").json()
    assert usage["projects"] == [{"id": project["id"], "name": "uses it"}] and usage["components"] == []
    assert client.delete("/api/components/test-source").status_code == 204
    assert client.get("/api/components/test-source/usage").status_code == 404
