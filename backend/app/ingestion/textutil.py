from __future__ import annotations

import re

_WS = re.compile(r"[ \t ]+")
_NON_ALNUM = re.compile(r"[^a-z0-9%$]+")


def clean_text(text: str) -> str:
    lines = [_WS.sub(" ", ln).strip() for ln in (text or "").splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


def normalize(text: str) -> str:
    return _NON_ALNUM.sub(" ", (text or "").lower()).strip()


def _luminance(rgb: tuple[float, float, float]) -> float:
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    for line in (text or "").splitlines():
        line = line.strip(" •-–—*\t")
        if not line:
            continue
        for piece in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line):
            piece = piece.strip()
            if piece:
                parts.append(piece)
    return parts


def truncate(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
