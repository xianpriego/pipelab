"""Shared fixtures: the real GStreamer catalog of the test container and an API client."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipelab.catalog.service import CatalogService
from pipelab.catalog.store import Catalog
from pipelab.graph.analyzer import Analyzer
from tests.api_client import CACHE_DIR, api_client


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return CatalogService(CACHE_DIR).load_blocking()


@pytest.fixture(scope="session")
def analyzer(catalog: Catalog) -> Analyzer:
    return Analyzer(catalog)


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest) -> Path:
    """An isolated data directory per test module."""
    return tmp_path_factory.mktemp(request.module.__name__.rsplit(".", 1)[-1])


@pytest.fixture(scope="module")
def client(catalog: Catalog, data_dir: Path) -> Iterator[TestClient]:
    with api_client(data_dir) as client:
        yield client
