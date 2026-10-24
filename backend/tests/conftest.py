"""Shared fixtures: the real GStreamer catalog of the test container."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipelab.catalog.service import CatalogService
from pipelab.catalog.store import Catalog
from pipelab.graph.analyzer import Analyzer

CACHE_DIR = Path(os.environ.get("PIPELAB_TEST_CACHE", "/tmp/pipelab-test-cache"))


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return CatalogService(CACHE_DIR).load_blocking()


@pytest.fixture(scope="session")
def analyzer(catalog: Catalog) -> Analyzer:
    return Analyzer(catalog)
