"""Score arithmetic and anchoring-study metrics.

The anchoring metrics are recorded for later analysis. They describe what
happened; they do not by themselves establish that anchoring occurred.
"""

from __future__ import annotations

from typing import Any

from ..models import RubricCriterion


def weighted_score(scores: list[dict[str, Any]], criteria: list[RubricCriterion], scale_max: int) -> float:
    """Weighted score on a 0–100 scale from per-criterion scores on 1..scale_max."""
    by_id = {int(s["criterion_id"]): float(s["score"]) for s in scores}
    total_weight = sum(c.weight for c in criteria) or 1.0
    value = sum(c.weight * (by_id[c.id] / scale_max) for c in criteria if c.id in by_id)
    return round(100 * value / total_weight, 1)


def validate_scores(
    scores: list[dict[str, Any]], criteria: list[RubricCriterion], scale_max: int
) -> list[dict[str, Any]]:
    ids = {c.id for c in criteria}
    seen: dict[int, dict[str, Any]] = {}
    for s in scores:
        cid = int(s["criterion_id"])
        if cid not in ids:
            raise ValueError(f"Unknown criterion {cid}")
        score = float(s["score"])
        if not (1 <= score <= scale_max):
            raise ValueError(f"Scores must be between 1 and {scale_max}")
        if (score * 2) != int(score * 2):
            raise ValueError("Scores must be whole or half points")
        seen[cid] = {"criterion_id": cid, "score": score, "comment": (s.get("comment") or "").strip()[:4000]}
    missing = ids - set(seen)
    if missing:
        names = ", ".join(c.name for c in criteria if c.id in missing)
        raise ValueError(f"Please score every criterion (missing: {names})")
    return [seen[c.id] for c in criteria]


def anchoring_metrics(initial: float, ai: float | None, revised: float) -> dict[str, Any]:
    initial_to_revised = round(revised - initial, 1)
    if ai is None:
        return {
            "initial_to_ai_difference": None,
            "initial_to_revised_difference": initial_to_revised,
            "revision_direction": "ai_unavailable",
        }
    initial_to_ai = round(ai - initial, 1)
    if initial_to_revised == 0:
        direction = "no_change"
    elif initial_to_ai != 0 and (initial_to_revised > 0) == (initial_to_ai > 0):
        direction = "toward_ai"
    else:
        direction = "away_from_ai"
    return {
        "initial_to_ai_difference": initial_to_ai,
        "initial_to_revised_difference": initial_to_revised,
        "revision_direction": direction,
    }
