import pytest

from pipelab.graph.layout import auto_layout
from pipelab.storage.media import MediaNotFound, MediaStore
from pipelab.storage.models import ProjectCreate, ProjectSettings, ProjectUpdate
from pipelab.storage.projects import ProjectNotFound, ProjectStore
from tests.helpers import chain, graph


def test_project_store_round_trip(tmp_path):
    store = ProjectStore(tmp_path)
    created = store.create(ProjectCreate(name="  "), chain("videotestsrc", "fakesink"))
    assert created.name == "Untitled pipeline"
    updated = store.update(created.id, ProjectUpdate(settings=ProjectSettings(gst_debug="*:4")))
    assert updated.settings.gst_debug == "*:4" and updated.graph == created.graph
    assert updated.updated_at >= created.updated_at
    assert [s.id for s in store.list()] == [created.id]
    assert store.list()[0].node_count == 2
    store.delete(created.id)
    with pytest.raises(ProjectNotFound):
        store.get(created.id)


def test_project_ids_cannot_escape_the_directory(tmp_path):
    with pytest.raises(ProjectNotFound):
        ProjectStore(tmp_path).get("../../etc/passwd")


def test_media_store_rejects_traversal(tmp_path):
    store = MediaStore(tmp_path / "media")
    with pytest.raises(MediaNotFound):
        store.file("../secret")


def test_layout_places_nodes_left_to_right(catalog):
    g = graph(
        [("src", "videotestsrc"), ("t", "tee"), ("a", "fakesink"), ("b", "fakesink")],
        [("src", "src", "t", "sink"), ("t", "src_0", "a", "sink"), ("t", "src_1", "b", "sink")],
    )
    positions = {n.id: n.position for n in auto_layout(g).nodes}
    assert positions["src"].x < positions["t"].x < positions["a"].x == positions["b"].x
    assert positions["a"].y != positions["b"].y
