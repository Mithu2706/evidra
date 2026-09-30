"""End-to-end API flow:

organizer creates rubric → uploads submission → ingestion → evidence pack →
AI brief → judge opens (AI score hidden) → submits → reveal → revise →
revision recorded → audit history available.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.auth_routes import DEMO_PASSWORD
from app.auth import hash_password
from app.db import SessionLocal, init_db
from app.models import Organization, User
from app.seed.demo_decks import DECKS, build_pdf
from app.services import processing


@pytest.fixture(scope="module")
def client(tmp_root, monkeypatch_module):
    # Process synchronously inside the request for deterministic tests.
    monkeypatch_module.setattr(processing, "enqueue_processing", processing.process_submission)
    monkeypatch_module.setattr(processing, "enqueue_analysis", processing.analyze_submission)
    from app.main import app

    init_db()
    with SessionLocal() as db:
        org = Organization(name="Test Org")
        db.add(org)
        db.flush()
        for email, role in [("org@test.dev", "organizer"), ("judge@test.dev", "judge"), ("judge2@test.dev", "judge")]:
            db.add(User(organization_id=org.id, email=email, name=email.split("@")[0].title(), role=role,
                        password_hash=hash_password(DEMO_PASSWORD)))
        db.commit()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def contains_key(obj, key):
    if isinstance(obj, dict):
        return key in obj or any(contains_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_key(v, key) for v in obj)
    return False


def test_full_flow(client, tmp_root):
    org = login(client, "org@test.dev")
    judge = login(client, "judge@test.dev")

    # Rubric weights must add to 100.
    bad = client.post("/api/rounds", headers=org, json={
        "name": "Bad", "criteria": [{"name": "A", "weight": 60}, {"name": "B", "weight": 30}]})
    assert bad.status_code == 422

    r = client.post("/api/rounds", headers=org, json={
        "name": "Pilot Round", "description": "Test", "judges_per_submission": 1,
        "criteria": [
            {"name": "Problem Understanding", "weight": 20}, {"name": "Innovation", "weight": 25},
            {"name": "Technical Feasibility", "weight": 20}, {"name": "Impact", "weight": 20},
            {"name": "Scalability", "weight": 15},
        ]})
    assert r.status_code == 201, r.text
    rnd = r.json()
    criteria = rnd["criteria"]

    # Judges cannot use organizer endpoints.
    assert client.get("/api/rounds", headers=judge).status_code == 403

    # Upload a submission (processed synchronously in tests).
    deck = next(d for d in DECKS if d.key == "greenledger")
    pdf = tmp_root / "greenledger.pdf"
    build_pdf(deck, pdf)
    with pdf.open("rb") as fh:
        r = client.post(f"/api/rounds/{rnd['id']}/submissions", headers=org,
                        data={"team_name": "Carbon Commons", "title": "GreenLedger"},
                        files={"file": ("greenledger.pdf", fh, "application/pdf")})
    assert r.status_code == 201, r.text
    sub_id = r.json()["id"]

    detail = client.get(f"/api/submissions/{sub_id}", headers=org).json()
    assert detail["submission"]["status"] == "ready"
    assert detail["integrity"]["status"] == "suspicious_instruction_detected"
    assert len(detail["document"]["slides"]) == len(deck.slides)
    assert detail["analysis"]["status"] == "completed"
    assert detail["ai_assessment"] is None  # hidden from organizers until judging completes

    # Wrong extension/content is rejected.
    r = client.post(f"/api/rounds/{rnd['id']}/submissions", headers=org, data={"team_name": "X"},
                    files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 422

    # Assign the judge.
    r = client.post(f"/api/rounds/{rnd['id']}/assignments/auto", headers=org, json={})
    assert r.json()["created"] >= 1
    dash = client.get("/api/judge/dashboard", headers=judge).json()
    item = next(a for a in dash["assignments"] if a["submission"]["id"] == sub_id)
    aid = item["id"]

    # Open: brief present, no scores anywhere.
    review = client.get(f"/api/judge/assignments/{aid}", headers=judge).json()
    brief = review["analysis"]["brief"]
    assert brief["verify_these"] and brief["verify_these"][0]["type"] == "integrity"
    for v in brief["verify_these"]:
        if v["type"] in ("unsupported_claim", "feasibility_gap"):
            assert v["evidence"], "evidence-backed findings must link to a slide"
            assert v["evidence"][0]["slide_id"].startswith("slide_")
    assert review["reveal"] is None
    for key in ("score", "overall_score", "ai_score", "assessment"):
        assert not contains_key(review, key), f"{key} leaked before submission"

    # Reveal before submitting is refused.
    assert client.post(f"/api/judge/assignments/{aid}/reveal", headers=judge).status_code == 403

    # Disagree with a finding.
    fk = f"verify:{brief['verify_these'][1]['id']}"
    r = client.put(f"/api/judge/assignments/{aid}/findings/{fk}", headers=judge,
                   json={"response": "disagree", "note": "Market size is cited in the appendix I have."})
    assert r.status_code == 200

    # Incomplete scores are rejected.
    r = client.post(f"/api/judge/assignments/{aid}/submit", headers=judge,
                    json={"criterion_scores": [{"criterion_id": criteria[0]["id"], "score": 6}]})
    assert r.status_code == 422

    initial = [6, 5, 4, 5, 5]
    r = client.post(f"/api/judge/assignments/{aid}/submit", headers=judge, json={
        "criterion_scores": [{"criterion_id": c["id"], "score": s, "comment": ""} for c, s in zip(criteria, initial)],
        "overall_comment": "Interesting but unsupported impact figures.", "recommendation": "discuss"})
    assert r.status_code == 200, r.text
    assert r.json()["assignment"]["status"] == "submitted"
    assert r.json()["reveal"] is None

    # Reveal.
    r = client.post(f"/api/judge/assignments/{aid}/reveal", headers=judge).json()
    reveal = r["reveal"]
    assert reveal["ai_available"] is True
    assert reveal["assessment"]["label"] == "AI-generated assessment — not a final decision."
    ai_score = reveal["ai_score"]
    assert ai_score is not None

    # Finalizing twice / without reveal is guarded; revise with a reason.
    revised = [6, 5, 4, 4, 5]
    r = client.post(f"/api/judge/assignments/{aid}/finalize", headers=judge, json={
        "decision": "revise", "reason": "Impact claims lack evidence.",
        "revised_scores": [{"criterion_id": c["id"], "score": s} for c, s in zip(criteria, revised)]})
    assert r.status_code == 200, r.text
    rev = r.json()["revision"]
    assert rev["decision"] == "revised"
    assert rev["human_initial_score"] == 50.0
    assert rev["human_revised_score"] == 48.0
    assert rev["ai_score"] == ai_score
    assert rev["initial_to_revised_difference"] == -2.0
    assert rev["revision_direction"] in ("toward_ai", "away_from_ai")
    assert r.json()["assignment"]["status"] == "completed"
    again = client.post(f"/api/judge/assignments/{aid}/finalize", headers=judge, json={"decision": "keep"})
    assert again.status_code == 409

    # Organizer sees results now that judging is complete, without a ranking.
    results = client.get(f"/api/rounds/{rnd['id']}/results", headers=org).json()
    row = next(x for x in results["rows"] if x["submission_id"] == sub_id)
    assert row["judging_complete"] and row["human_final_mean"] == 48.0
    assert row["ai_score"] == ai_score
    assert not contains_key(results, "rank")
    csv = client.get(f"/api/rounds/{rnd['id']}/results/anchoring.csv", headers=org)
    assert "human_initial_score" in csv.text and "50.0" in csv.text

    # Rubric is locked once evaluations exist.
    r = client.put(f"/api/rounds/{rnd['id']}/criteria", headers=org,
                   json={"criteria": [{"name": "Only", "weight": 100}]})
    assert r.status_code == 409

    # Audit trail covers the whole flow.
    events = client.get(f"/api/rounds/{rnd['id']}/audit", headers=org, params={"submission_id": sub_id}).json()
    actions = {e["action"] for e in events["events"]}
    for expected in ("submission.uploaded", "submission.ingested", "integrity.flagged", "analysis.completed",
                     "assignment.created", "review.opened", "finding.responded", "evaluation.submitted",
                     "ai.revealed", "evaluation.revised"):
        assert expected in actions, expected


def test_other_judge_cannot_access_assignment(client):
    other = login(client, "judge2@test.dev")
    assert client.get("/api/judge/assignments/1", headers=other).status_code == 404
    assert client.get("/api/submissions/1/file", headers=other).status_code == 404


def test_ai_failure_is_reported_not_fabricated(client, tmp_root, monkeypatch):
    from app.ai import pipeline as pipeline_mod
    from app.ai.providers.base import LLMError

    class Broken:
        engine, model = "anthropic", "test"

        def run(self, ctx):
            raise pipeline_mod.AnalysisFailed(str(LLMError("Could not reach the model provider")))

    monkeypatch.setattr(processing, "build_pipeline", lambda settings: Broken())
    org = login(client, "org@test.dev")
    rounds = client.get("/api/rounds", headers=org).json()
    deck = next(d for d in DECKS if d.key == "studybuddy")
    pdf = tmp_root / "studybuddy.pdf"
    build_pdf(deck, pdf)
    with pdf.open("rb") as fh:
        r = client.post(f"/api/rounds/{rounds[0]['id']}/submissions", headers=org,
                        data={"team_name": "Night Owls"}, files={"file": ("studybuddy.pdf", fh, "application/pdf")})
    detail = client.get(f"/api/submissions/{r.json()['id']}", headers=org).json()
    assert detail["analysis"]["status"] == "failed"
    assert detail["analysis"]["message"] == "AI analysis unavailable. Human review can continue."
    assert "brief" not in detail["analysis"]
    # Slides are still available for human review.
    assert detail["document"]["slides"]
