"""Global component library: one JSON document per component."""

from __future__ import annotations

import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

from pipelab.components.models import Component

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class ComponentNotFound(KeyError):
    pass


class InvalidComponentId(ValueError):
    pass


class ComponentStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._revision = 0

    @property
    def revision(self) -> int:
        """Changes whenever a component is saved or deleted (cache key)."""
        return self._revision

    def _path(self, component_id: str) -> Path:
        if not _ID.match(component_id):
            raise InvalidComponentId(
                f"'{component_id}' is not a valid id (lowercase letters, digits, dashes)"
            )
        return self._directory / f"{component_id}.json"

    def all(self) -> dict[str, Component]:
        components = {}
        for path in sorted(self._directory.glob("*.json")):
            try:
                component = Component.model_validate_json(path.read_text())
            except ValueError:
                continue
            components[component.id] = component
        return components

    def get(self, component_id: str) -> Component:
        path = self._path(component_id)
        if not path.exists():
            raise ComponentNotFound(component_id)
        return Component.model_validate_json(path.read_text())

    def save(self, component: Component) -> Component:
        with self._lock:
            path = self._path(component.id)
            previous = Component.model_validate_json(path.read_text()) if path.exists() else None
            saved = component.model_copy(
                update={"version": (previous.version + 1) if previous else 1, "updated_at": datetime.now(UTC)}
            )
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(saved.model_dump_json(indent=2))
            os.replace(temporary, path)
            self._revision += 1
            return saved

    def delete(self, component_id: str) -> None:
        with self._lock:
            path = self._path(component_id)
            if not path.exists():
                raise ComponentNotFound(component_id)
            path.unlink()
            self._revision += 1
