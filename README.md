# Evidra — human-in-the-loop judge copilot

> **Let AI prepare the evidence. Let humans make the decision.**

Evidra turns every hackathon or innovation-challenge submission (PDF / PPTX) into an
evidence-backed **Judge Brief**. Judges still read and score every submission themselves; the AI
score stays hidden until they have submitted their own evaluation.

```
Submission → Ingestion → Evidence Pack → AI Analysis → Judge Brief → Human Decision
```

Evidra is **not** an autonomous judge. It does not rank submissions, reject them, or select
winners. It is designed to reduce repetitive judging work while keeping humans responsible for
every decision. We have not run the pilot evaluation yet, so we make no performance claims.

---

## Quick start

Requirements: Python 3.11+, Node 20+. Optional but recommended: **LibreOffice** (with Impress)
to render PPTX slides. PDF rendering and OCR work with pip packages only.

```bash
make install                 # pip + npm install
make backend                 # API on http://localhost:8000 (seeds demo data on first start, ~30–60 s)
make frontend                # UI on http://localhost:5173
```

Open http://localhost:5173 and choose a demo account on the sign-in page
(password `evidra-demo`):

| Account | Role | Good for |
| --- | --- | --- |
| `marcus@demo.evidra.app` | Judge | Four fresh assignments — walk the full judge flow |
| `elena@demo.evidra.app` | Judge | Completed reviews, incl. a revision after AI reveal |
| `sam@demo.evidra.app` | Judge | One completed, one in progress |
| `dana@demo.evidra.app` | Organizer | Round setup, uploads, assignments, progress, results, audit |

Single-process alternative: `make build` then `make backend` — the API serves the built UI at
http://localhost:8000.

CI (GitHub Actions, `.github/workflows/ci.yml`) runs the backend tests, checks that `shared/schemas`
is up to date, and typechecks and builds the frontend on every push to `main` and every pull request.

Other commands: `make test` (pytest + typecheck), `make reset` (drop & reseed), `make schemas`
(export shared JSON Schemas), `make demo-files` (write the demo decks to `demo-submissions/` so you
can upload them yourself).

### Using Claude for analysis

By default the analysis runs on an **offline rule-based analyzer** (no API key, no model calls,
clearly labelled as such in the UI). To use Claude:

```bash
cp .env.example .env
# set EVIDRA_AI_ENGINE=anthropic and ANTHROPIC_API_KEY=...
```

The key stays on the server. Output is constrained with structured outputs, validated against
Pydantic schemas and grounded against the Evidence Pack before anything is stored. The Claude
path is covered by tests using a fake provider; it has not been exercised against the live API in
this repository's CI.

---

## Demo data

Six fictional submissions (all teams, people and figures are invented):

| Team | File | Demonstrates |
| --- | --- | --- |
| Route Zero — BinSight | PDF | Clear structure; unsupported 40 % cost claim; unexplained hardware assumption |
| Triage Labs — MediQueue | PPTX | Strong validation data; speaker notes |
| Carbon Commons — GreenLedger | PDF | Hidden white-on-white instruction → **integrity warning**, withheld from AI |
| Clearwater Collective — AquaSense | PPTX | Image-only slides + external video link → **partially assessed** |
| Night Owls — StudyBuddy | PDF | Vague deck; rubric criteria with no evidence → "Not assessed" |
| Metro Movers — ParkPal | PDF | Truncated upload → "Document could not be fully processed. Manual review required." |

Some evaluations are pre-completed (through the same API a judge uses) so dashboards, results and
the audit trail have data.

---

## The judge workflow

The evaluation screen has three panes: **original document** (left), **Judge Brief** (centre),
**evaluation form** (right).

1. Open a submission. The brief leads with **Verify These** — source-linked evidence checks grouped by
   priority (priority = how much human attention a finding deserves, not a judgment of the
   submission) — followed by strengths, **Not Assessed** (material Evidra could not reliably
   evaluate), **Submission Integrity** (hidden/inconsistent content only), an evidence map and a
   rubric map (no scores).
2. Clicking **View Slide 6** jumps the viewer to that slide and shows the cited excerpt.
3. Agree / disagree / unsure with any strength or Verify-These item, with an optional note.
4. Score each criterion. **The AI score is hidden** — the server does not include it in any
   response until the evaluation is submitted (enforced in `backend/app/api/judge_routes.py`).
5. Submit → the AI assessment is revealed, labelled *"AI-generated assessment — not a final
   decision."*
6. **Keep my score** or **Revise my score** (optional reason). Initial score, AI score, revised
   score, reason and timestamps are stored, with `initial_to_ai_difference`,
   `initial_to_revised_difference` and `revision_direction` computed for the anchoring study.

Organizers can export the anchoring dataset as CSV from the Results tab. These data are
descriptive; they do not by themselves demonstrate anchoring.

---

## Architecture (summary)

```
backend/app
├── ingestion/          validation → parser (PDF: PyMuPDF, PPTX: python-pptx) → renderer
│   │                   → OCR (RapidOCR / Tesseract) → integrity analyzer → EvidencePack
│   └── sources/        interfaces for future GitHub (V2), website & video (V3) sources — not implemented
├── ai/
│   ├── providers/      LLMProvider interface + Anthropic implementation
│   ├── stages/         Extractor, RubricAnalyzer, Verifier, BriefWriter
│   │   ├── heuristic/  offline rule-based implementations
│   │   └── llm/        provider-agnostic LLM implementations + prompts
│   ├── grounding.py    drops refs to unknown slides, verifies excerpts
│   ├── brief.py        deterministic assembly (integrity, not-assessed, rubric map, AI score)
│   └── pipeline.py     orchestration; fails closed — never stores partial/fabricated results
├── schemas/            Pydantic contracts (Evidence Pack, AI outputs) → exported to /shared/schemas
├── services/           processing worker, scoring & anchoring metrics, reporting
├── api/                FastAPI routes (auth, organizer, judge, files)
├── models.py           SQLAlchemy models (User, Organization, EvaluationRound, RubricCriterion,
│                       Submission, SubmissionFile, Slide, Evidence, AIAnalysis, JudgeAssignment,
│                       HumanEvaluation, FindingResponse, AIReveal, Revision, AuditEvent)
└── seed/               fictional demo decks + seed script
frontend/src            React + TypeScript + Tailwind (Vite)
shared/schemas          JSON Schemas generated from the backend models
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design decisions, the integrity check and
extension points.

## Limitations (V1)

- Integrity checking compares the text layer with OCR of rendered slides, adds structural
  visibility checks and scans speaker notes. It cannot detect every form of manipulation and is
  described accordingly in the UI.
- OCR reads text inside images; charts and diagrams are not interpreted (reported as "Not assessed").
- External links, embedded media, GitHub repositories, demos and videos are not analyzed.
- The rule-based analyzer locates evidence and flags claims with transparent text rules; it does
  not understand content the way a language model does. Its preliminary scores are coarse.
- Processing runs in an in-process thread pool and uses SQLite — fine for a pilot, not for scale.
- Authentication is a minimal signed-token scheme; production use should sit behind SSO.
