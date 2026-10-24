"""Application services shared by the HTTP routers."""

from __future__ import annotations

import threading

from fastapi import Request

from pipelab.catalog.service import CatalogService
from pipelab.catalog.store import Catalog
from pipelab.components.models import Component
from pipelab.components.overlay import overlay_catalog
from pipelab.components.starters import StarterComponents
from pipelab.config import Settings
from pipelab.graph.analyzer import Analyzer
from pipelab.runtime.session import RuntimeManager
from pipelab.storage.components import ComponentStore
from pipelab.storage.media import MediaStore
from pipelab.storage.projects import ProjectStore
from pipelab.templates.service import TemplateService


class Services:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.catalog = CatalogService(settings.cache_dir, settings.catalog_build_timeout)
        self.projects = ProjectStore(settings.projects_dir)
        self.media = MediaStore(settings.media_dir)
        self.runtime = RuntimeManager(settings.media_dir)
        self.components = ComponentStore(settings.data_dir / "components")
        self._lock = threading.Lock()
        self._analyzer: Analyzer | None = None
        self._analyzer_key: tuple[int, int] | None = None
        self._templates: TemplateService | None = None
        self._starters: StarterComponents | None = None

    def analyzer(self) -> Analyzer:
        """Analyzer over the catalog plus the component library; raises ``CatalogNotReady``."""
        base = self.catalog.catalog
        key = (id(base), self.components.revision)
        with self._lock:
            if self._analyzer is None or self._analyzer_key != key:
                components = self.components.all()
                self._analyzer = Analyzer(overlay_catalog(base, components), components)
                self._analyzer_key = key
            return self._analyzer

    def full_catalog(self) -> Catalog:
        """GStreamer elements plus one virtual element per library component."""
        return self.analyzer().catalog

    def component_definitions(self) -> dict[str, Component]:
        return self.analyzer().components

    def templates(self) -> TemplateService:
        catalog = self.catalog.catalog
        with self._lock:
            if self._templates is None:
                self._templates = TemplateService(catalog)
            return self._templates

    def starters(self) -> StarterComponents:
        catalog = self.catalog.catalog
        with self._lock:
            if self._starters is None:
                self._starters = StarterComponents(catalog)
            return self._starters


def get_services(request: Request) -> Services:
    return request.app.state.services
