"""TestClient factory with an isolated data directory and a warm catalog cache."""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from pipelab.config import Settings
from pipelab.main import create_app

CACHE_DIR = Path(os.environ.get("PIPELAB_TEST_CACHE", "/tmp/pipelab-test-cache"))


@contextmanager
def api_client(data_dir: Path) -> Iterator[TestClient]:
    settings = Settings(data_dir=data_dir)
    settings.ensure_dirs()
    for cached in CACHE_DIR.glob("catalog-*.json"):
        shutil.copy(cached, settings.cache_dir / cached.name)
    with TestClient(create_app(settings)) as client:
        deadline = time.monotonic() + 120
        while client.get("/api/health").json()["catalog"]["state"] != "ready":
            assert time.monotonic() < deadline, "catalog was not built in time"
            time.sleep(0.2)
        yield client
