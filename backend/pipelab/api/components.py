"""Component library (macro blocks), grouping a selection and expanding instances."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel

from pipelab.api.services import Services, get_services
from pipelab.components.bundle import Bundle, bundle_of, conflicts
from pipelab.components.grouping import expand_instance, group_into_component
from pipelab.components.models import Component, component_id, references
from pipelab.components.starters import StarterInfo
from pipelab.components.validate import validate_component
from pipelab.graph.models import Graph, Issue

router = APIRouter()
ServicesDep = Annotated[Services, Depends(get_services)]


class SelectionRequest(BaseModel):
    graph: Graph
    node_ids: list[str]
    id: str
    name: str = ""


class SelectionResponse(BaseModel):
    component: Component
    graph: Graph


class ExpandRequest(BaseModel):
    graph: Graph
    node_id: str


class ExpandResponse(BaseModel):
    graph: Graph


class ImportRequest(BaseModel):
    bundle: Bundle
    overwrite: bool = False


class ImportResult(BaseModel):
    imported: list[str]


class ComponentIssues(BaseModel):
    issues: list[Issue]


class UsageEntry(BaseModel):
    id: str
    name: str


class ComponentUsage(BaseModel):
    """Who breaks when the component is deleted."""

    components: list[UsageEntry]
    projects: list[UsageEntry]


@router.post("/components/validate")
def validate(component: Annotated[Component, Body(embed=True)], services: ServicesDep) -> ComponentIssues:
    return ComponentIssues(issues=validate_component(services.analyzer(), component))


@router.get("/components")
def list_components(services: ServicesDep) -> list[Component]:
    return sorted(services.components.all().values(), key=lambda c: c.name.lower())


@router.get("/components/starters")
def list_starters(services: ServicesDep) -> list[StarterInfo]:
    return services.starters().list()


@router.post("/components/starters/{starter_id}", status_code=201)
def install_starter(starter_id: str, services: ServicesDep) -> Component:
    """Copies a starter component into the library (409 if that id is taken)."""
    definition = services.starters().definition(starter_id)
    if definition.id in services.components.all():
        raise HTTPException(409, f"'{definition.id}' is already in the library")
    return services.components.save(definition)


@router.post("/components/import")
def import_components(request: ImportRequest, services: ServicesDep) -> ImportResult:
    """Saves the components of a file; 409 lists those already in the library unless ``overwrite``."""
    taken = conflicts(request.bundle, services.components.all())
    if taken and not request.overwrite:
        raise HTTPException(409, f"already in the library: {', '.join(taken)}")
    saved = [services.components.save(component).id for component in request.bundle.components]
    return ImportResult(imported=saved)


@router.get("/components/{component_id}/bundle")
def export_component(component_id: str, services: ServicesDep) -> Bundle:
    return bundle_of(services.components.get(component_id), services.components.all())


@router.get("/components/{component_id}")
def get_component(component_id: str, services: ServicesDep) -> Component:
    return services.components.get(component_id)


@router.put("/components/{component_id}")
def save_component(component_id: str, component: Component, services: ServicesDep) -> Component:
    if component.id != component_id:
        raise HTTPException(422, "the id in the body does not match the URL")
    return services.components.save(component)


@router.get("/components/{component_id}/usage")
def component_usage(component_id: str, services: ServicesDep) -> ComponentUsage:
    services.components.get(component_id)
    components = [
        UsageEntry(id=c.id, name=c.name)
        for c in services.components.all().values()
        if references(c.graph, component_id)
    ]
    projects = []
    for summary in services.projects.list():
        if references(services.projects.get(summary.id).graph, component_id):
            projects.append(UsageEntry(id=summary.id, name=summary.name))
    return ComponentUsage(components=components, projects=projects)


@router.delete("/components/{component_id}", status_code=204)
def delete_component(component_id: str, services: ServicesDep) -> Response:
    services.components.delete(component_id)
    return Response(status_code=204)


@router.post("/components/from-selection", status_code=201)
def from_selection(request: SelectionRequest, services: ServicesDep) -> SelectionResponse:
    if request.id in services.components.all():
        raise HTTPException(409, f"a component named '{request.id}' already exists")
    component, graph = group_into_component(request.graph, request.node_ids, request.id, request.name)
    return SelectionResponse(component=services.components.save(component), graph=graph)


@router.post("/graph/expand")
def expand(request: ExpandRequest, services: ServicesDep) -> ExpandResponse:
    node = request.graph.node(request.node_id)
    definition = component_id(node.factory) if node else None
    if definition is None:
        raise HTTPException(422, "the node is not a component instance")
    return ExpandResponse(
        graph=expand_instance(request.graph, request.node_id, services.components.get(definition))
    )
