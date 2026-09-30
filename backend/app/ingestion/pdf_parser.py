"""PDF parsing with PyMuPDF: text, titles, links, images and text-visibility signals."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from .base import DocumentParser, IngestionError, ParsedDocument, ParsedUnit, TextSpanSignal
from .textutil import clean_text, contrast_ratio

fitz.TOOLS.mupdf_display_errors(False)

TINY_FONT_PT = 3.0
LOW_CONTRAST_RATIO = 1.35


class PDFParser(DocumentParser):
    file_types = ("pdf",)
    name = "pymupdf"

    def parse(self, path: Path, work_dir: Path) -> ParsedDocument:
        try:
            doc = fitz.open(path)
        except Exception as exc:  # corrupt / truncated file
            raise IngestionError("The PDF could not be opened; the file appears damaged or incomplete.") from exc
        if doc.needs_pass:
            raise IngestionError("PDF is password protected.")
        if doc.page_count == 0:
            raise IngestionError("PDF has no pages.")

        units: list[ParsedUnit] = []
        for index, page in enumerate(doc):
            unit = ParsedUnit(page_number=index + 1)
            try:
                self._parse_page(page, unit)
            except Exception as exc:  # keep going; mark page partially processed
                unit.processing_notes.append(f"Text extraction failed on this page: {exc}")
            units.append(unit)

        return ParsedDocument(
            file_type="pdf",
            units=units,
            renderable_pdf=path,
            render_page_map={i: i for i in range(len(units))},
            notes=["Speaker notes are not available for PDF submissions."],
            metadata={k: v for k, v in (doc.metadata or {}).items() if v},
        )

    def _parse_page(self, page: fitz.Page, unit: ParsedUnit) -> None:
        unit.text = clean_text(page.get_text("text"))
        unit.title = self._title(page)
        unit.links = sorted({lk["uri"] for lk in page.get_links() if lk.get("uri")})
        unit.has_visual_content = bool(page.get_images(full=True))
        for annot in page.annots() or []:
            if annot.type[1] in ("RichMedia", "Movie", "Screen", "Sound"):
                unit.has_embedded_media = True
        unit.structural_signals = self._visibility_signals(page)

    @staticmethod
    def _title(page: fitz.Page) -> str | None:
        best: tuple[float, str] | None = None
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line.get("spans", [])).strip()
                if not text or not line.get("spans"):
                    continue
                size = max(s["size"] for s in line["spans"])
                if best is None or size > best[0] + 0.5:
                    best = (size, text)
        return best[1][:200] if best else None

    @staticmethod
    def _visibility_signals(page: fitz.Page) -> list[TextSpanSignal]:
        """Find text that is present in the text layer but unlikely to be visible."""
        signals: list[TextSpanSignal] = []
        try:
            traces = page.get_texttrace()
        except Exception:
            return signals
        if not traces:
            return signals

        scale = 0.5
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        page_rect = page.rect

        def region_median(bbox) -> tuple[float, float, float] | None:
            x0, y0, x1, y1 = (int(v * scale) for v in bbox)
            x0, y0 = max(x0, 0), max(y0, 0)
            x1, y1 = min(max(x1, x0 + 1), pix.width), min(max(y1, y0 + 1), pix.height)
            samples = [
                pix.pixel(x, y)
                for x in range(x0, x1, max(1, (x1 - x0) // 12))
                for y in range(y0, y1, max(1, (y1 - y0) // 4))
            ]
            if not samples:
                return None
            samples.sort(key=sum)
            r, g, b = samples[len(samples) // 2][:3]
            return (r / 255, g / 255, b / 255)

        for span in traces:
            text = "".join(chr(c[0]) for c in span.get("chars", []) if c[0] > 0).strip()
            if len(text) < 3:
                continue
            bbox = fitz.Rect(span["bbox"])
            if span.get("type") == 3 or span.get("opacity", 1) == 0:
                signals.append(TextSpanSignal(text, "invisible_text_layer", "Text uses an invisible render mode."))
                continue
            if span.get("size", 12) < TINY_FONT_PT:
                signals.append(TextSpanSignal(text, "tiny_text", f"Font size {span['size']:.1f}pt."))
                continue
            if not bbox.intersects(page_rect):
                signals.append(TextSpanSignal(text, "off_slide_content", "Text is positioned outside the page."))
                continue
            color = span.get("color")
            if color and len(color) == 3:
                bg = region_median(bbox & page_rect)
                if bg is not None and contrast_ratio(tuple(color), bg) < LOW_CONTRAST_RATIO:
                    signals.append(
                        TextSpanSignal(text, "low_contrast_text", "Text colour is nearly identical to the background.")
                    )
        return _merge_signals(signals)


def _merge_signals(signals: list[TextSpanSignal]) -> list[TextSpanSignal]:
    """Adjacent spans with the same reason are merged into one readable excerpt."""
    merged: list[TextSpanSignal] = []
    for sig in signals:
        if merged and merged[-1].reason == sig.reason:
            merged[-1].text = f"{merged[-1].text} {sig.text}"
        else:
            merged.append(TextSpanSignal(sig.text, sig.reason, sig.detail))
    return merged
