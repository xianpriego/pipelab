"""Pipeline execution: start/pause/stop, live properties, events WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect

from pipelab.api.services import Services, get_services
from pipelab.components.models import Component, component_id, used_components
from pipelab.graph.models import Graph, Node
from pipelab.graph.property_check import check_value
from pipelab.runtime.models import LinkToggle, PropertyChange, RuntimeStatus, StartRequest, StopRequest
from pipelab.runtime.session import RuntimeCommandError, RuntimeSession
from pipelab.storage.projects import ProjectNotFound

router = APIRouter(prefix="/projects/{project_id}/runtime")
ServicesDep = Annotated[Services, Depends(get_services)]


def _session(project_id: str, services: Services) -> RuntimeSession:
    services.projects.get(project_id)  # 404 for unknown projects
    return services.runtime.session(project_id)


@router.get("/status")
def status(project_id: str, services: ServicesDep) -> RuntimeStatus:
    return _session(project_id, services).status


@router.post("/start")
async def start(project_id: str, request: StartRequest, services: ServicesDep) -> RuntimeStatus:
    session = _session(project_id, services)
    project = services.projects.get(project_id)
    graph = request.graph or project.graph
    if not graph.nodes:
        raise HTTPException(422, "the pipeline is empty")
    components = used_components(graph, services.component_definitions())
    await session.start(
        graph,
        request.gst_debug or project.settings.gst_debug,
        components={key: value.model_dump(mode="json") for key, value in components.items()},
    )
    return session.status


async def _command(project_id: str, services: Services, command: dict[str, Any]) -> RuntimeStatus:
    session = _session(project_id, services)
    try:
        await session.send(command)
    except RuntimeCommandError as error:
        raise HTTPException(409, str(error)) from error
    return session.status


async def _request(project_id: str, services: Services, command: dict[str, Any]) -> dict[str, Any]:
    """A command answered by the worker; 409 when the pipeline is not running."""
    try:
        return await _session(project_id, services).request(command)
    except RuntimeCommandError as error:
        raise HTTPException(409, str(error)) from error


@router.post("/play")
async def play(project_id: str, services: ServicesDep) -> RuntimeStatus:
    return await _command(project_id, services, {"cmd": "play"})


@router.post("/pause")
async def pause(project_id: str, services: ServicesDep) -> RuntimeStatus:
    return await _command(project_id, services, {"cmd": "pause"})


@router.post("/stop")
async def stop(project_id: str, request: StopRequest, services: ServicesDep) -> RuntimeStatus:
    session = _session(project_id, services)
    await session.stop(request.mode)
    return session.status


def _running_node(graph: Graph, node_id: str, components: dict[str, Component]) -> Node | None:
    """The node behind a runtime id; ``"<instance>/<inner>"`` ids are looked up in components."""
    *path, local = node_id.split("/")
    for instance_id in path:
        instance = graph.node(instance_id)
        definition = components.get(component_id(instance.factory) or "") if instance else None
        if definition is None:
            return None
        graph = definition.graph
    return graph.node(local)


def _validate_change(services: Services, session: RuntimeSession, change: PropertyChange) -> None:
    """Reject changes the running element cannot take (checked against the graph that is running)."""
    if session.graph is None or change.pad:
        return
    node = _running_node(session.graph, change.node_id, services.component_definitions())
    element = services.full_catalog().get(node.factory) if node else None
    if element is None:
        return
    prop = element.property(change.property)
    if prop is None or not prop.writable or prop.construct_only:
        raise HTTPException(422, f"'{change.property}' cannot be changed on a running {element.name}")
    if (error := check_value(prop, change.value)) is not None:
        raise HTTPException(422, error)


@router.post("/property")
async def set_property(project_id: str, change: PropertyChange, services: ServicesDep) -> dict[str, Any]:
    _validate_change(services, _session(project_id, services), change)
    return await _request(project_id, services, {"cmd": "set_property", **change.model_dump()})


@router.get("/properties/{node_id:path}")
async def properties(project_id: str, node_id: str, services: ServicesDep) -> dict[str, Any]:
    data = await _request(project_id, services, {"cmd": "get_properties", "node_id": node_id})
    return {"node_id": node_id, **data}


@router.post("/tap")
async def tap(project_id: str, request: LinkToggle, services: ServicesDep) -> dict[str, Any]:
    """Preview what flows through a link."""
    return await _request(project_id, services, {"cmd": "tap", **request.model_dump()})


@router.post("/probe")
async def probe(project_id: str, request: LinkToggle, services: ServicesDep) -> dict[str, Any]:
    """Record the buffers and events crossing a link (sent as ``probe`` events)."""
    return await _request(project_id, services, {"cmd": "probe", **request.model_dump()})


@router.get("/dot")
async def dot(project_id: str, services: ServicesDep) -> Response:
    data = await _request(project_id, services, {"cmd": "dot"})
    process = await asyncio.create_subprocess_exec(
        "dot", "-Tsvg", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
    )
    svg, _ = await process.communicate(data["dot"].encode())
    return Response(svg, media_type="image/svg+xml")


@router.websocket("/ws")
async def events(websocket: WebSocket, project_id: str) -> None:
    services: Services = websocket.app.state.services
    try:
        services.projects.get(project_id)
    except ProjectNotFound:
        await websocket.close(code=4404)  # before accept: the handshake is refused
        return
    session = services.runtime.session(project_id)
    await websocket.accept()
    queue = session.subscribe()
    try:
        while True:
            kind, message = await queue.get()
            if kind == "bytes":
                await websocket.send_bytes(message)
            else:
                await websocket.send_text(message)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        session.unsubscribe(queue)
        with contextlib.suppress(RuntimeError):
            await websocket.close()
