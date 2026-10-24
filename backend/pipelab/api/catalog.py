"""Health, element catalog and starter templates."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from pipelab.api.services import Services, get_services
from pipelab.catalog.models import ElementInfo
from pipelab.gst import Gst
from pipelab.templates.info import StarterInfo

router = APIRouter()
ServicesDep = Annotated[Services, Depends(get_services)]


@router.get("/health")
def health(services: ServicesDep) -> dict[str, Any]:
    status = services.catalog.status
    return {
        "status": "ok",
        "gstreamer_version": Gst.version_string(),
        "catalog": {
            "state": status.state,
            "done": status.done,
            "total": status.total,
            "count": status.count,
            "error": status.error,
        },
    }


@router.get("/catalog")
def catalog(services: ServicesDep) -> dict[str, Any]:
    summaries = services.full_catalog().summaries()
    return {"elements": [summary.model_dump() for summary in summaries]}


@router.get("/catalog/{factory}")
def element(factory: str, services: ServicesDep) -> ElementInfo:
    info = services.full_catalog().get(factory)
    if info is None:
        raise HTTPException(404, f"element '{factory}' is not installed")
    return info


@router.get("/templates")
def templates(services: ServicesDep) -> list[StarterInfo]:
    return services.templates().list()
