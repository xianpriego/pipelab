"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    catalog_build_timeout: float = 30.0

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def components_dir(self) -> Path:
        return self.data_dir / "components"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    def ensure_dirs(self) -> None:
        for path in (self.projects_dir, self.components_dir, self.media_dir, self.cache_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("PIPELAB_DATA_DIR", "/data")),
        catalog_build_timeout=float(os.environ.get("PIPELAB_CATALOG_ELEMENT_TIMEOUT", "30")),
    )
