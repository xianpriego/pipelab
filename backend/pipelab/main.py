"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from pipelab.api import catalog, components, graph, media, monitor, projects, runtime
from pipelab.api.services import Services
from pipelab.catalog.service import CatalogNotReady
from pipelab.components.grouping import GroupingError
from pipelab.components.starters import StarterNotFound
from pipelab.config import Settings, get_settings
from pipelab.graph.fixes import FixError
from pipelab.storage.components import ComponentNotFound, InvalidComponentId
from pipelab.storage.media import MediaNotFound
from pipelab.storage.projects import ProjectNotFound
from pipelab.storage.samples import ensure_sample_media
from pipelab.templates.service import TemplateNotFound

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_ERRORS: dict[type[Exception], tuple[int, str]] = {
    CatalogNotReady: (503, "The GStreamer element catalog is still being built, retry in a few seconds."),
    ProjectNotFound: (404, "Project not found."),
    TemplateNotFound: (404, "Template not found."),
    MediaNotFound: (404, "File not found."),
    FixError: (400, ""),
    ComponentNotFound: (404, "Component not found."),
    StarterNotFound: (404, "Starter component not found."),
    InvalidComponentId: (422, ""),
    GroupingError: (422, ""),
}


def _install_error_handlers(app: FastAPI) -> None:
    for error_type, (status, detail) in _ERRORS.items():

        async def handler(_request: Request, error: Exception, status=status, detail=detail) -> JSONResponse:
            return JSONResponse({"detail": detail or str(error)}, status_code=status)

        app.add_exception_handler(error_type, handler)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.ensure_dirs()
        services = Services(settings)
        app.state.services = services
        services.catalog.start()
        ensure_sample_media(settings.media_dir)
        yield
        await services.runtime.shutdown()

    app = FastAPI(
        title="Pipelab",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    for module in (catalog, components, projects, graph, runtime, media, monitor):
        app.include_router(module.router, prefix="/api")
    _install_error_handlers(app)
    return app


app = create_app()
