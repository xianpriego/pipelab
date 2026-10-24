"""Media files: uploads used as pipeline inputs and files pipelines produce."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipelab.api.services import Services, get_services
from pipelab.storage.media import MediaFile

router = APIRouter(prefix="/media")
ServicesDep = Annotated[Services, Depends(get_services)]


class MediaList(BaseModel):
    files: list[MediaFile]


@router.get("")
def list_media(services: ServicesDep) -> MediaList:
    return MediaList(files=services.media.list())


@router.post("", status_code=201)
def upload(file: UploadFile, services: ServicesDep) -> MediaFile:
    return services.media.save(file.filename or "upload.bin", file.file)


@router.get("/{path:path}")
def download(path: str, services: ServicesDep) -> FileResponse:
    return FileResponse(services.media.file(path))


@router.delete("/{path:path}", status_code=204)
def delete(path: str, services: ServicesDep) -> Response:
    services.media.delete(path)
    return Response(status_code=204)
