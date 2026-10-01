"""Original documents and rendered slide images (organizers and assigned judges)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Slide, User
from ..services.storage import is_within_storage
from .deps import current_user, get_submission_for

router = APIRouter(prefix="/api", tags=["files"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _serve(path: str | None, media_type: str, filename: str | None = None, inline: bool = True) -> FileResponse:
    if not path or not is_within_storage(path) or not Path(path).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not available")
    disposition = "inline" if inline else "attachment"
    return FileResponse(path, media_type=media_type, filename=filename, content_disposition_type=disposition,
                        headers={"Cache-Control": "private, max-age=3600"})


@router.get("/submissions/{submission_id}/file")
def original_file(submission_id: int, download: bool = False, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    sub = get_submission_for(db, submission_id, user)
    f = sub.primary_file
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file")
    return _serve(f.stored_path, MEDIA_TYPES.get(f.file_type, "application/octet-stream"), f.original_filename,
                  inline=not download and f.file_type == "pdf")


@router.get("/submissions/{submission_id}/rendered.pdf")
def rendered_pdf(submission_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = get_submission_for(db, submission_id, user)
    f = sub.primary_file
    path = (f.rendered_pdf_path or (f.stored_path if f.file_type == "pdf" else None)) if f else None
    return _serve(path, "application/pdf")


@router.get("/slides/{slide_id}/image")
def slide_image(slide_id: int, variant: str = Query(default="full", pattern="^(full|thumb)$"),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    slide = db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slide not found")
    get_submission_for(db, slide.submission_id, user)  # authorization
    return _serve(slide.thumb_path if variant == "thumb" else slide.image_path, "image/png")
