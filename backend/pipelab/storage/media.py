"""Files in the media directory: pipeline inputs (uploads) and outputs."""

from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel

mimetypes.add_type("application/vnd.apple.mpegurl", ".m3u8")
mimetypes.add_type("video/mp2t", ".ts")
mimetypes.add_type("video/x-matroska", ".mkv")
mimetypes.add_type("audio/ogg", ".opus")


class MediaFile(BaseModel):
    path: str
    size: int
    modified: float
    mime: str


class MediaNotFound(KeyError):
    pass


class MediaStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str) -> Path:
        """Absolute path inside the media directory; rejects path traversal."""
        root = self.directory.resolve()
        path = (root / relative).resolve()
        if path != root and root not in path.parents:
            raise MediaNotFound(relative)
        return path

    def _describe(self, path: Path) -> MediaFile:
        stat = path.stat()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        relative = path.relative_to(self.directory.resolve()).as_posix()
        return MediaFile(path=relative, size=stat.st_size, modified=stat.st_mtime, mime=mime)

    def list(self) -> list[MediaFile]:
        root = self.directory.resolve()
        files = [
            p
            for p in root.rglob("*")
            if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)
        ]
        return sorted((self._describe(p) for p in files), key=lambda f: f.modified, reverse=True)

    def file(self, relative: str) -> Path:
        path = self.resolve(relative)
        if not path.is_file():
            raise MediaNotFound(relative)
        return path

    def save(self, filename: str, data: BinaryIO) -> MediaFile:
        path = self.resolve(Path(filename).name)
        temporary = path.with_name(f".{path.name}.upload")
        with temporary.open("wb") as target:
            shutil.copyfileobj(data, target)
        temporary.replace(path)
        return self._describe(path)

    def delete(self, relative: str) -> None:
        self.file(relative).unlink()
