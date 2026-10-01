# Evidra architecture

## Principles that shape the code

| Principle | Where it is enforced |
| --- | --- |
| Never an autonomous judge; no ranking | No ranking fields anywhere; results sorted alphabetically (`services/reporting.py`) |
| AI score hidden until the judge submits | `api/judge_routes.py` — only `reveal_out` serializes the assessment, and it is gated on a submitted `HumanEvaluation` + `AIReveal` record. Organizers see AI scores only after all assigned judges finish. |
| Every finding links to a slide | `ai/grounding.py` drops refs to unknown slide ids and verifies excerpts; `ai/pipeline.py` drops evidence-required findings with no remaining source |
| "Not assessed" instead of guessing | `ingestion/pipeline.py` emits `NotAssessedItem`s; criteria without evidence get `assessed=false, score=null` and are excluded from the AI total (with the assessed weight disclosed) |
| Humans can disagree with everything | `FindingResponse` per strength / verify item; keep-or-revise after reveal |
| AI failure never blocks review | Pipeline fails closed (`AnalysisFailed`) → UI shows "AI analysis unavailable. Human review can continue." |
| Structured output only | All stages return Pydantic models; LLM output is schema-constrained and re-validated |
| Replaceable AI provider | `ai/providers/base.py::LLMProvider`; stages depend only on that interface |

## Ingestion → Evidence Pack

```
FileValidator (magic bytes, size, type)       ingestion/validation.py
DocumentParser  PDF: PyMuPDF                   ingestion/pdf_parser.py
                PPTX: python-pptx (+ notes)    ingestion/pptx_parser.py
PageRenderer    PDF → PNG (PPTX via LibreOffice → PDF)   ingestion/rendering.py
OCREngine       RapidOCR | Tesseract | none    ingestion/ocr.py
IntegrityAnalyzer                              ingestion/integrity.py
→ EvidencePack (schemas/evidence.py)
```

Each unit has a stable id (`slide_06`), `source_type` (`slide` today; `document`, `github`,
`video`, `website` reserved) and a `source_location` (`slide_number`, `page_number`,
`file_path`, `timestamp`, `url`). Future sources implement `ingestion/sources/base.py::SourceIngestor`
(placeholders in `sources/future.py` raise `SourceNotSupported`).

## Integrity check (V1)

1. Each text-layer line (≥ 3 words) is fuzzy-matched (`rapidfuzz.partial_ratio`) against the OCR
   of the rendered slide.
2. Structural signals: invisible PDF render mode / zero opacity, text colour ≈ background (sampled
   from the render), fonts < 3–4 pt, boxes outside the slide, hidden PPTX shapes/slides.
3. Speaker notes are scanned separately (they are legitimately invisible).
4. Escalation: only hidden or unrendered text that **resembles an instruction to evaluators**
   becomes `suspicious_instruction_detected`; it is withheld from all AI stages. Other
   discrepancies are `potential_discrepancy`; isolated OCR misses are tolerated. Visible text that
   addresses judges is informational only. If rendering/OCR is unavailable the status is
   `manual_review_required`.
5. Language is cautious: "No hidden-content discrepancy detected", never "clean".

## AI analysis

```
Extractor ──► RubricAnalyzer ──► Verifier ──► BriefWriter ──► assemble_brief / assemble_assessment
   (grounded after every stage)
```

- Heuristic and LLM implementations of each stage share the same interfaces and output schemas.
- The integrity section, Not Assessed, evidence map and rubric coverage are assembled by code, so a
  model can never invent or remove them. Integrity findings are always prepended to Verify These.
- The LLM receives the Evidence Pack as delimited XML with untrusted-content instructions; withheld
  text is replaced by `[content withheld by integrity check]`.
- Anthropic provider: `client.beta.messages.stream` with adaptive thinking, `output_config.format`
  JSON schema, and server-side refusal fallbacks. Invalid output gets one corrective retry, then
  the analysis fails.

## Human evaluation data model

`HumanEvaluation` (immutable, pre-reveal) → `AIReveal` (what was shown, when) → `Revision`
(kept/revised, reason, anchoring metrics, seconds since reveal). Every step writes an `AuditEvent`.

## Extending

- **New AI vendor:** implement `LLMProvider.generate_json`, add a branch in `ai/pipeline.py::build_pipeline`.
- **New OCR engine / parser / renderer:** implement the interface in `ingestion/base.py` and pass it
  to `IngestionPipeline`.
- **New evidence source (V2/V3):** implement `SourceIngestor`, emit `EvidenceUnit`s with the right
  `source_type`/`source_location`, and add a viewer for that location kind.
