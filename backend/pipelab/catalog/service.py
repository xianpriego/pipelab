"""Loads the catalog from cache or builds it in the background."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pipelab.catalog.build import build_catalog, registry_hash
from pipelab.catalog.models import CatalogData
from pipelab.catalog.store import Catalog
from pipelab.storage.files import atomic_write

log = logging.getLogger(__name__)

CatalogState = Literal["idle", "building", "ready", "error"]


@dataclass
class CatalogStatus:
    state: CatalogState = "idle"
    done: int = 0
    total: int = 0
    error: str | None = None
    count: int = 0


class CatalogNotReady(RuntimeError):
    pass


class CatalogService:
    def __init__(self, cache_dir: Path, element_timeout: float = 30.0) -> None:
        self._cache_dir = cache_dir
        self._element_timeout = element_timeout
        self._catalog: Catalog | None = None
        self._lock = threading.Lock()
        self.status = CatalogStatus()

    @property
    def catalog(self) -> Catalog:
        if self._catalog is None:
            raise CatalogNotReady("the element catalog is still being built")
        return self._catalog

    @property
    def ready(self) -> bool:
        return self._catalog is not None

    def start(self) -> None:
        """Load or build the catalog in a background thread."""
        with self._lock:
            if self.status.state in ("building", "ready"):
                return
            self.status = CatalogStatus(state="building")
        threading.Thread(target=self._load, name="catalog-builder", daemon=True).start()

    def load_blocking(self) -> Catalog:
        self.start()
        while self.status.state == "building":
            threading.Event().wait(0.2)
        return self.catalog

    def _cache_path(self) -> Path:
        return self._cache_dir / f"catalog-{registry_hash()}.json"

    def _progress(self, done: int, total: int) -> None:
        self.status.done, self.status.total = done, total

    @staticmethod
    def _cached(path: Path) -> CatalogData | None:
        """The cached catalog; an unreadable cache is deleted so it gets rebuilt."""
        if not path.exists():
            return None
        try:
            return CatalogData.model_validate_json(path.read_text())
        except ValueError:
            log.warning("discarding unreadable catalog cache %s", path.name)
            path.unlink(missing_ok=True)
            return None

    def _load(self) -> None:
        try:
            path = self._cache_path()
            data = self._cached(path)
            if data is None:
                log.info("building GStreamer element catalog (cache miss: %s)", path.name)
                data = build_catalog(self._element_timeout, self._progress)
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                atomic_write(path, data.model_dump_json())
            self._catalog = Catalog(data)
            self.status.state, self.status.count = "ready", len(self._catalog)
            log.info("catalog ready: %d elements", len(self._catalog))
        except Exception as error:  # surfaced through /api/health
            log.exception("catalog build failed")
            self.status.state, self.status.error = "error", str(error)
