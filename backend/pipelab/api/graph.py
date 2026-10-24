"""Graph analysis: link checks, validation, fixes, layout, export and import."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pipelab.api.services import Services, get_services
from pipelab.export import FORMATS, export_graph
from pipelab.export.models import ExportFormat, ExportRequest, ExportResult, ImportRequest, ImportResult
from pipelab.graph.fixes import apply_fix
from pipelab.graph.layout import auto_layout
from pipelab.graph.link_check import check_link
from pipelab.graph.models import Edge, Fix, Graph, Issue, LinkCheckResult
from pipelab.graph.validate import validate_graph
from pipelab.importer import import_gst_launch

router = APIRouter()
ServicesDep = Annotated[Services, Depends(get_services)]


class LinkRequest(BaseModel):
    graph: Graph
    edge: Edge


class GraphRequest(BaseModel):
    graph: Graph


class FixRequest(BaseModel):
    graph: Graph
    fix: Fix


class GraphResponse(BaseModel):
    graph: Graph


class ValidationResponse(BaseModel):
    issues: list[Issue]


@router.post("/graph/check-link")
def check(request: LinkRequest, services: ServicesDep) -> LinkCheckResult:
    return check_link(services.analyzer(), request.graph, request.edge)


@router.post("/graph/validate")
def validate(request: GraphRequest, services: ServicesDep) -> ValidationResponse:
    return ValidationResponse(issues=validate_graph(services.analyzer(), request.graph))


@router.post("/graph/apply-fix")
def fix(request: FixRequest, services: ServicesDep) -> GraphResponse:
    return GraphResponse(graph=apply_fix(services.analyzer(), request.graph, request.fix))


@router.post("/graph/layout")
def layout(request: GraphRequest) -> GraphResponse:
    return GraphResponse(graph=auto_layout(request.graph))


@router.get("/export/formats")
def export_formats() -> list[ExportFormat]:
    return FORMATS


@router.post("/export")
def export(request: ExportRequest, services: ServicesDep) -> ExportResult:
    try:
        return export_graph(
            request.graph,
            services.full_catalog(),
            request.format,
            request.name,
            components=services.component_definitions(),
        )
    except KeyError as error:
        raise HTTPException(404, f"unknown export format '{request.format}'") from error


@router.post("/import/gst-launch")
def import_description(request: ImportRequest, services: ServicesDep) -> ImportResult:
    if not request.description.strip():
        raise HTTPException(422, "the pipeline description is empty")
    return import_gst_launch(request.description, services.full_catalog())
