"""File helpers shared by the stores and the catalog cache."""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write(path: Path, text: str) -> None:
    """Write ``text`` so readers see the old or the new content, never a partial file."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text)
    os.replace(temporary, path)
