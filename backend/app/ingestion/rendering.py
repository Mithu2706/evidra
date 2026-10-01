"""Rasterise pages/slides to images for the viewer, OCR and integrity checks."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from .base import PageRenderer, ParsedDocument, RenderedPage

THUMB_WIDTH = 360


class PyMuPDFRenderer(PageRenderer):
    name = "pymupdf"

    def __init__(self, width_px: int = 1600):
        self.width_px = width_px

    def render(self, doc: ParsedDocument, out_dir: Path) -> list[RenderedPage]:
        out_dir.mkdir(parents=True, exist_ok=True)
        if doc.renderable_pdf is None:
            return [RenderedPage(None, None, "Rendering unavailable") for _ in doc.units]

        results: list[RenderedPage] = []
        with fitz.open(doc.renderable_pdf) as pdf:
            for idx, unit in enumerate(doc.units):
                page_idx = doc.render_page_map.get(idx)
                if page_idx is None or page_idx >= pdf.page_count:
                    reason = "Hidden slide — not rendered" if unit.hidden else "No rendered page for this slide"
                    results.append(RenderedPage(None, None, reason))
                    continue
                try:
                    page = pdf[page_idx]
                    key = f"slide_{unit.page_number:02d}"
                    full = out_dir / f"{key}.png"
                    thumb = out_dir / f"{key}_thumb.png"
                    zoom = self.width_px / page.rect.width
                    page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(full)
                    tz = THUMB_WIDTH / page.rect.width
                    page.get_pixmap(matrix=fitz.Matrix(tz, tz), alpha=False).save(thumb)
                    results.append(RenderedPage(full, thumb))
                except Exception as exc:
                    results.append(RenderedPage(None, None, f"Rendering failed: {exc}"))
        return results
