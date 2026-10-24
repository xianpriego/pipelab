"""Projects persisted as one JSON document per project."""

from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pipelab.graph.models import Graph
from pipelab.storage.models import Project, ProjectCreate, ProjectSummary, ProjectUpdate

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ProjectNotFound(KeyError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class ProjectStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, project_id: str) -> Path:
        if not _ID.match(project_id):
            raise ProjectNotFound(project_id)
        return self._directory / f"{project_id}.json"

    def _write(self, project: Project) -> Project:
        path = self._path(project.id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(project.model_dump_json(indent=2))
        os.replace(temporary, path)
        return project

    def list(self) -> list[ProjectSummary]:
        summaries = []
        for path in self._directory.glob("*.json"):
            try:
                project = Project.model_validate_json(path.read_text())
            except ValueError:
                continue
            summaries.append(
                ProjectSummary(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    node_count=len(project.graph.nodes),
                )
            )
        return sorted(summaries, key=lambda s: s.updated_at, reverse=True)

    def get(self, project_id: str) -> Project:
        path = self._path(project_id)
        if not path.exists():
            raise ProjectNotFound(project_id)
        return Project.model_validate_json(path.read_text())

    def create(self, request: ProjectCreate, graph: Graph | None = None) -> Project:
        now = _now()
        project = Project(
            id=uuid.uuid4().hex[:12],
            name=request.name.strip() or "Untitled pipeline",
            description=request.description,
            created_at=now,
            updated_at=now,
            graph=graph or request.graph or Graph(),
        )
        with self._lock:
            return self._write(project)

    def update(self, project_id: str, patch: ProjectUpdate) -> Project:
        with self._lock:
            project = self.get(project_id)
            changes = patch.model_dump(exclude_unset=True, exclude_none=True)
            updated = Project.model_validate({**project.model_dump(), **changes, "updated_at": _now()})
            return self._write(updated)

    def delete(self, project_id: str) -> None:
        with self._lock:
            path = self._path(project_id)
            if not path.exists():
                raise ProjectNotFound(project_id)
            path.unlink()

    def duplicate(self, project_id: str) -> Project:
        original = self.get(project_id)
        copy = ProjectCreate(name=f"{original.name} (copy)", description=original.description)
        project = self.create(copy, original.graph)
        return self.update(project.id, ProjectUpdate(settings=original.settings))
