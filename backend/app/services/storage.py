"""Filesystem layout for uploaded and derived files (outside the web root)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ..config import get_settings


def submission_dir(submission_id: int) -> Path:
    path = get_settings().storage_dir / "submissions" / str(submission_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def work_dir(submission_id: int) -> Path:
    path = submission_dir(submission_id) / "derived"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reset_work_dir(submission_id: int) -> Path:
    path = submission_dir(submission_id) / "derived"
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(submission_id: int, source, original_filename: str) -> tuple[Path, int, str]:
    """Stream an upload to disk. Returns (path, size, sha256)."""
    ext = Path(original_filename).suffix.lower()[:10]
    target = submission_dir(submission_id) / f"original{ext}"
    digest = hashlib.sha256()
    size = 0
    with target.open("wb") as out:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            out.write(chunk)
    return target, size, digest.hexdigest()


def is_within_storage(path: str | Path) -> bool:
    root = get_settings().storage_dir.resolve()
    try:
        Path(path).resolve().relative_to(root)
    except ValueError:
        return False
    return True
