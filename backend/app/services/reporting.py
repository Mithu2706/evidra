"""Organizer dashboard, aggregate results and anchoring-study export.

V1 deliberately shows no winner ranking: results are listed alphabetically
and emphasise judge agreement rather than position.
"""

from __future__ import annotations

import csv
import io
import statistics
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent, EvaluationRound, JudgeAssignment, Submission, User, aware
from .processing import AI_FAILURE_MESSAGE

PROCESSED = {"ready", "partially_processed"}
SPREAD_THRESHOLD = 15.0  # points on the 0-100 scale


def _review_minutes(a: JudgeAssignment) -> float | None:
    if a.opened_at and a.submitted_at:
        return (aware(a.submitted_at) - aware(a.opened_at)).total_seconds() / 60
    return None


def submission_stage(s: Submission) -> str:
    if s.status in ("uploaded", "processing"):
        return "processing"
    if s.status == "processing_failed" and not s.assignments:
        return "failed"
    if s.assignments and all(a.status == "completed" for a in s.assignments):
        return "completed"
    if any(a.status != "assigned" for a in s.assignments):
        return "in_review"
    return "awaiting_review"


def dashboard(db: Session, rnd: EvaluationRound) -> dict[str, Any]:
    subs = list(rnd.submissions)
    assignments = [a for s in subs for a in s.assignments]
    stages = [submission_stage(s) for s in subs]
    minutes = [m for a in assignments if (m := _review_minutes(a)) is not None]

    attention: list[dict[str, Any]] = []
    integrity_warnings = ai_failures = 0
    for s in subs:
        a = s.latest_analysis
        if s.status == "processing_failed":
            attention.append({"submission_id": s.id, "team_name": s.team_name, "kind": "processing_failed",
                              "reason": s.processing_error or "Document could not be processed."})
        elif s.status == "partially_processed":
            attention.append({"submission_id": s.id, "team_name": s.team_name, "kind": "partial",
                              "reason": "Document partially processed; some content was not assessed."})
        if s.integrity_status in ("potential_discrepancy", "suspicious_instruction_detected", "manual_review_required") \
                and s.status != "processing_failed":
            integrity_warnings += 1
            summary = ((s.evidence_pack or {}).get("integrity") or {}).get("summary") or "Integrity warning"
            attention.append({"submission_id": s.id, "team_name": s.team_name, "kind": "integrity", "reason": summary})
        if a is not None and a.status == "failed":
            ai_failures += 1
            attention.append({"submission_id": s.id, "team_name": s.team_name, "kind": "ai_failed",
                              "reason": AI_FAILURE_MESSAGE})
        if s.status in PROCESSED and not s.assignments:
            attention.append({"submission_id": s.id, "team_name": s.team_name, "kind": "unassigned",
                              "reason": "No judges assigned yet."})

    judges: dict[int, dict[str, Any]] = {}
    for a in assignments:
        j = judges.setdefault(a.judge_id, {"id": a.judge_id, "name": a.judge.name, "assigned": 0, "completed": 0,
                                           "in_progress": 0, "_minutes": []})
        j["assigned"] += 1
        j["completed"] += a.status == "completed"
        j["in_progress"] += a.status in ("in_progress", "submitted")
        if (m := _review_minutes(a)) is not None:
            j["_minutes"].append(m)
    judge_rows = []
    for j in judges.values():
        m = j.pop("_minutes")
        j["avg_review_minutes"] = round(statistics.mean(m), 1) if m else None
        judge_rows.append(j)

    recent = db.scalars(
        select(AuditEvent).where(AuditEvent.round_id == rnd.id).order_by(AuditEvent.created_at.desc()).limit(8)
    ).all()

    completed_assignments = sum(a.status == "completed" for a in assignments)
    total = len(subs)
    completed = stages.count("completed")
    return {
        "totals": {
            "submissions": total,
            "processed": sum(s.status in PROCESSED for s in subs),
            "processing": stages.count("processing"),
            "failed": sum(s.status == "processing_failed" for s in subs),
            "awaiting_review": stages.count("awaiting_review"),
            "in_review": stages.count("in_review"),
            "completed": completed,
            "remaining": total - completed,
        },
        "assignments": {
            "total": len(assignments),
            "completed": completed_assignments,
            "in_progress": sum(a.status in ("in_progress", "submitted") for a in assignments),
            "not_started": sum(a.status == "assigned" for a in assignments),
            "completion_pct": round(100 * completed_assignments / len(assignments), 1) if assignments else 0.0,
        },
        "avg_review_minutes": round(statistics.mean(minutes), 1) if minutes else None,
        "integrity_warnings": integrity_warnings,
        "ai_failures": ai_failures,
        "attention": attention,
        "judges": sorted(judge_rows, key=lambda j: j["name"]),
        "recent_activity": [
            {"id": e.id, "action": e.action, "actor": e.actor_label, "submission_id": e.submission_id,
             "created_at": aware(e.created_at).isoformat()}
            for e in recent
        ],
    }


def results(rnd: EvaluationRound) -> dict[str, Any]:
    rows = []
    revisions = []
    for s in sorted(rnd.submissions, key=lambda x: x.team_name.lower()):
        done = [a for a in s.assignments if a.status == "completed" and a.revision]
        complete = bool(s.assignments) and len(done) == len(s.assignments)
        finals = [a.revision.human_revised_score for a in done]
        initials = [a.evaluation.weighted_score for a in done if a.evaluation]
        recs: dict[str, int] = {}
        for a in done:
            if a.evaluation and a.evaluation.recommendation:
                recs[a.evaluation.recommendation] = recs.get(a.evaluation.recommendation, 0) + 1
        revisions.extend(a.revision for a in done)
        analysis = s.latest_analysis
        spread = round(max(finals) - min(finals), 1) if len(finals) > 1 else None
        rows.append({
            "submission_id": s.id,
            "team_name": s.team_name,
            "title": s.title,
            "judging_complete": complete,
            "judges_completed": len(done),
            "judges_assigned": len(s.assignments),
            "human_final_mean": round(statistics.mean(finals), 1) if complete and finals else None,
            "human_initial_mean": round(statistics.mean(initials), 1) if complete and initials else None,
            "human_final_min": min(finals) if complete and finals else None,
            "human_final_max": max(finals) if complete and finals else None,
            "spread": spread if complete else None,
            "needs_calibration": bool(complete and spread is not None and spread >= SPREAD_THRESHOLD),
            "recommendations": recs if complete else {},
            "revisions": sum(1 for a in done if a.revision.decision == "revised"),
            # AI score is shown to organizers only once human judging is complete.
            "ai_score": analysis.ai_overall_score if complete and analysis and analysis.status == "completed" else None,
            "integrity_status": s.integrity_status,
        })

    with_ai = [r for r in revisions if r.ai_score is not None]
    changed = [r for r in revisions if r.decision == "revised"]
    summary = {
        "evaluations_finalized": len(revisions),
        "kept": sum(r.decision == "kept" for r in revisions),
        "revised": len(changed),
        "toward_ai": sum(r.revision_direction == "toward_ai" for r in revisions),
        "away_from_ai": sum(r.revision_direction == "away_from_ai" for r in revisions),
        "ai_unavailable": sum(r.revision_direction == "ai_unavailable" for r in revisions),
        "mean_abs_initial_to_ai": round(statistics.mean(abs(r.initial_to_ai_difference) for r in with_ai), 1)
        if with_ai else None,
        "mean_abs_revised_to_ai": round(statistics.mean(abs(r.ai_score - r.human_revised_score) for r in with_ai), 1)
        if with_ai else None,
        "mean_abs_revision": round(statistics.mean(abs(r.initial_to_revised_difference) for r in changed), 1)
        if changed else None,
        "note": "Descriptive data for later analysis. Movement toward the AI score after reveal is consistent "
        "with, but does not by itself demonstrate, anchoring.",
    }
    return {"rows": rows, "anchoring": summary}


ANCHORING_COLUMNS = [
    "round_id", "submission_id", "team_name", "judge_id", "judge_name", "opened_at", "submitted_at",
    "revealed_at", "finalized_at", "review_minutes", "human_initial_score", "ai_score", "human_revised_score",
    "decision", "revision_reason", "initial_to_ai_difference", "initial_to_revised_difference",
    "revision_direction", "seconds_since_reveal", "recommendation",
]


def anchoring_csv(db: Session, rnd: EvaluationRound) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ANCHORING_COLUMNS)
    writer.writeheader()
    for s in rnd.submissions:
        for a in s.assignments:
            r = a.revision
            if r is None:
                continue
            judge = db.get(User, a.judge_id)
            m = _review_minutes(a)
            writer.writerow({
                "round_id": rnd.id, "submission_id": s.id, "team_name": s.team_name,
                "judge_id": a.judge_id, "judge_name": judge.name if judge else "",
                "opened_at": aware(a.opened_at).isoformat() if a.opened_at else "",
                "submitted_at": aware(a.submitted_at).isoformat() if a.submitted_at else "",
                "revealed_at": aware(a.reveal.revealed_at).isoformat() if a.reveal else "",
                "finalized_at": aware(r.created_at).isoformat(),
                "review_minutes": round(m, 2) if m is not None else "",
                "human_initial_score": r.human_initial_score, "ai_score": r.ai_score,
                "human_revised_score": r.human_revised_score, "decision": r.decision,
                "revision_reason": r.revision_reason,
                "initial_to_ai_difference": r.initial_to_ai_difference,
                "initial_to_revised_difference": r.initial_to_revised_difference,
                "revision_direction": r.revision_direction,
                "seconds_since_reveal": r.seconds_since_reveal,
                "recommendation": a.evaluation.recommendation if a.evaluation else "",
            })
    return buf.getvalue()
