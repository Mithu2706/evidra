"""Seed a fictional organization, round, users and demo submissions.

Run with:  python -m app.seed.seed [--reset]

Demo accounts (password: evidra-demo)
    dana@demo.evidra.app    Organizer
    marcus@demo.evidra.app  Judge (four fresh assignments — use this one to walk the flow)
    elena@demo.evidra.app   Judge (completed reviews)
    sam@demo.evidra.app     Judge (mixed)

Some evaluations are pre-completed so dashboards and results have data. They
are produced by calling the same API functions a judge would use.
"""

from __future__ import annotations

import argparse
import logging
import shutil
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from ..api import judge_routes
from ..api.auth_routes import DEMO_PASSWORD
from ..auth import hash_password
from ..config import get_settings
from ..db import Base, SessionLocal, engine, init_db
from ..models import (
    AuditEvent,
    EvaluationRound,
    JudgeAssignment,
    Organization,
    RubricCriterion,
    Submission,
    SubmissionFile,
    User,
)
from ..services import processing, storage
from ..audit import record
from .demo_decks import build_all

log = logging.getLogger("evidra.seed")

CRITERIA = [
    ("Problem Understanding", "How clearly the team defines the problem, who experiences it and why it matters.", 20),
    ("Innovation", "Novelty of the approach and how it differs from existing solutions.", 25),
    ("Technical Feasibility", "Whether the solution can realistically be built and operated, with evidence.", 20),
    ("Impact", "Expected benefit for the target users or society, and how credibly it is supported.", 20),
    ("Scalability", "Ability to grow beyond a pilot: deployment path, costs, integration and business model.", 15),
]

USERS = [
    ("dana@demo.evidra.app", "Dana Okafor", "organizer", "Program Lead, Northbridge Innovation Network"),
    ("marcus@demo.evidra.app", "Marcus Lee", "judge", "Principal Engineer, civic technology"),
    ("elena@demo.evidra.app", "Elena Petrova", "judge", "Venture Partner"),
    ("sam@demo.evidra.app", "Sam Rivera", "judge", "Public Health Researcher"),
]

# (deck key, judge email, plan) — plan: None = not started, "open" = opened only,
# or (initial scores, decision, revised scores|None, reason, minutes)
PLANS: list[tuple[str, str, object]] = [
    ("binsight", "marcus", None),
    ("greenledger", "marcus", None),
    ("aquasense", "marcus", None),
    ("studybuddy", "marcus", None),
    ("binsight", "elena", ([7, 7, 6, 6, 7], "revise", [7, 7, 6, 5, 7],
                           "I had credited the 40% cost reduction; on re-reading slide 7 there is no supporting data.", 18)),
    ("mediqueue", "elena", ([8, 7, 8, 7, 6], "keep", None, "", 14)),
    ("studybuddy", "elena", ([3, 4, 2, 3, 2], "keep", None, "", 9)),
    ("mediqueue", "sam", ([7, 6, 9, 8, 6], "revise", [7, 6, 9, 7, 6],
                          "Impact figures are goals, not pilot results; lowered Impact by one point.", 22)),
    ("greenledger", "sam", "open"),
    ("aquasense", "sam", None),
]


def reset_database() -> None:
    Base.metadata.drop_all(engine)
    shutil.rmtree(get_settings().storage_dir / "submissions", ignore_errors=True)


def seed(*, reset: bool = False) -> None:
    if reset:
        reset_database()
    init_db()
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        if db.scalar(select(Organization.id).limit(1)) is not None:
            log.info("Database already contains data; skipping seed (use --reset to recreate).")
            return

        org = Organization(name="Northbridge Innovation Network")
        db.add(org)
        db.flush()
        users: dict[str, User] = {}
        for email, name, role, title in USERS:
            u = User(organization_id=org.id, email=email, name=name, role=role, title=title,
                     password_hash=hash_password(DEMO_PASSWORD))
            db.add(u)
            users[email.split("@")[0]] = u
        db.flush()
        dana = users["dana"]

        rnd = EvaluationRound(
            organization_id=org.id,
            name="Smart Cities & Sustainability Challenge 2026",
            description="Round 1 screening of pitch decks. Every submission is reviewed by two judges. "
            "Evidra prepares an evidence brief for each deck; judges score independently and remain "
            "responsible for every decision.",
            score_scale_max=10,
            max_submissions=200,
            max_file_size_mb=25,
            max_pages=30,
            allowed_file_types=["pdf", "pptx"],
            judges_per_submission=2,
            created_by_id=dana.id,
            created_at=now - timedelta(days=6),
        )
        rnd.criteria = [RubricCriterion(name=n, description=d, weight=w, position=i)
                        for i, (n, d, w) in enumerate(CRITERIA)]
        db.add(rnd)
        db.flush()
        record(db, "round.created", actor=dana, round_id=rnd.id, entity_type="round", entity_id=rnd.id,
               details={"name": rnd.name, "criteria": [{"name": n, "weight": w} for n, _, w in CRITERIA]})
        db.commit()

        decks_dir = get_settings().storage_dir / "demo-source"
        subs: dict[str, Submission] = {}
        for deck, path in build_all(decks_dir):
            sub = Submission(round_id=rnd.id, team_name=deck.team, title=deck.title, status="uploaded",
                             uploaded_by_id=dana.id, created_at=now - timedelta(days=4))
            db.add(sub)
            db.flush()
            with path.open("rb") as fh:
                stored, size, digest = storage.save_upload(sub.id, fh, deck.filename)
            db.add(SubmissionFile(submission_id=sub.id, original_filename=deck.filename, stored_path=str(stored),
                                  file_type=deck.file_type, size_bytes=size, sha256=digest))
            record(db, "submission.uploaded", actor=dana, round_id=rnd.id, submission_id=sub.id,
                   entity_type="submission", entity_id=sub.id,
                   details={"filename": deck.filename, "size_bytes": size, "sha256": digest})
            db.commit()
            subs[deck.key] = sub

        for key, sub in subs.items():
            log.info("Processing demo submission: %s", sub.team_name)
            processing.process_submission(sub.id)
        db.expire_all()

        for key, judge_key, plan in PLANS:
            sub = db.get(Submission, subs[key].id)
            judge = users[judge_key]
            a = JudgeAssignment(round_id=rnd.id, submission_id=sub.id, judge_id=judge.id, assigned_by_id=dana.id,
                                assigned_at=now - timedelta(days=3))
            db.add(a)
            db.flush()
            record(db, "assignment.created", actor=dana, round_id=rnd.id, submission_id=sub.id,
                   entity_type="assignment", entity_id=a.id, details={"judge": judge.name})
            db.commit()
            if plan is None:
                continue
            judge_routes.open_review(a.id, user=judge, db=db)
            if plan == "open":
                continue
            initial, decision, revised, reason, minutes = plan  # type: ignore[misc]
            criteria = rnd.criteria
            judge_routes.submit_evaluation(
                a.id,
                judge_routes.SubmitIn(
                    criterion_scores=[judge_routes.CriterionScoreIn(criterion_id=c.id, score=s)
                                      for c, s in zip(criteria, initial)],
                    overall_comment=_comment(key),
                    recommendation="advance" if sum(initial) >= 32 else "do_not_advance",
                ),
                user=judge, db=db,
            )
            judge_routes.reveal_ai(a.id, user=judge, db=db)
            judge_routes.finalize(
                a.id,
                judge_routes.FinalizeIn(
                    decision=decision,
                    revised_scores=[judge_routes.CriterionScoreIn(criterion_id=c.id, score=s)
                                    for c, s in zip(criteria, revised)] if revised else None,
                    reason=reason,
                ),
                user=judge, db=db,
            )
            _backdate(db, a, minutes, now)
        db.commit()
        log.info("Seed complete.")
    finally:
        db.close()


def _comment(key: str) -> str:
    return {
        "binsight": "Well-structured deck with a clear user and workflow. Impact numbers need evidence.",
        "mediqueue": "Strongest validation in the batch: held-out test and benchmark against the current display.",
        "studybuddy": "Idea is not yet developed; no technical or impact detail to assess.",
    }.get(key, "")


def _backdate(db, a: JudgeAssignment, minutes: int, now: datetime) -> None:
    """Spread the demo reviews over the previous two days for realistic dashboards."""
    offset = timedelta(hours=6 + (a.id * 7) % 40)
    opened = now - offset
    submitted = opened + timedelta(minutes=minutes)
    revealed = submitted + timedelta(seconds=20)
    finalized = revealed + timedelta(minutes=2)
    a.opened_at, a.submitted_at, a.completed_at = opened, submitted, finalized
    a.evaluation.submitted_at = submitted
    a.reveal.revealed_at = revealed
    a.revision.created_at = finalized
    a.revision.seconds_since_reveal = 120.0
    times = {"review.opened": opened, "evaluation.submitted": submitted, "ai.revealed": revealed,
             "evaluation.kept": finalized, "evaluation.revised": finalized}
    for action, ts in times.items():
        db.execute(update(AuditEvent)
                   .where(AuditEvent.entity_type == "assignment", AuditEvent.entity_id == a.id,
                          AuditEvent.action == action)
                   .values(created_at=ts))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Evidra demo data")
    parser.add_argument("--reset", action="store_true", help="drop all data first")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
