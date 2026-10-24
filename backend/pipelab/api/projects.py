"""Workspace (project) CRUD."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from pipelab.api.services import Services, get_services
from pipelab.storage.models import Project, ProjectCreate, ProjectSummary, ProjectUpdate

router = APIRouter(prefix="/projects")
ServicesDep = Annotated[Services, Depends(get_services)]


@router.get("")
def list_projects(services: ServicesDep) -> list[ProjectSummary]:
    return services.projects.list()


@router.post("", status_code=201)
def create_project(request: ProjectCreate, services: ServicesDep) -> Project:
    graph = services.templates().graph(request.template) if request.template else None
    return services.projects.create(request, graph)


@router.get("/{project_id}")
def get_project(project_id: str, services: ServicesDep) -> Project:
    return services.projects.get(project_id)


@router.put("/{project_id}")
def update_project(project_id: str, patch: ProjectUpdate, services: ServicesDep) -> Project:
    return services.projects.update(project_id, patch)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, services: ServicesDep) -> Response:
    services.projects.delete(project_id)
    await services.runtime.discard(project_id)
    return Response(status_code=204)


@router.post("/{project_id}/duplicate", status_code=201)
def duplicate_project(project_id: str, services: ServicesDep) -> Project:
    return services.projects.duplicate(project_id)
