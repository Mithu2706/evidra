"""Rule-based (offline) implementations of the four AI stages.

Used when no LLM provider is configured, and as a transparent baseline. All
text it produces is either extracted verbatim from the submission or filled
into fixed, neutral templates — it never invents facts about a submission.
"""

from __future__ import annotations

import re

from ....ingestion.textutil import truncate
from ....schemas.ai import (
    BriefWriterOutput,
    Claim,
    CriterionAssessment,
    EvidenceRef,
    ExtractionOutput,
    Issue,
    RubricAnalysisOutput,
    Strength,
    TopicEvidence,
    VerificationOutput,
    VerifyItem,
)
from ...context import AnalysisContext, UnitView
from ..base import BriefWriter, Extractor, RubricAnalyzer, Verifier
from . import signals as S

MAX_REFS_PER_TOPIC = 3
MAX_VERIFY_ITEMS = 8
# Topics where a single matching sentence is enough to count as (limited) evidence.
WEAK_FALLBACK_TOPICS = {"problem", "solution"}


def _slide_label(ctx: AnalysisContext, slide_id: str) -> str:
    view = ctx.view(slide_id)
    return f"Slide {view.unit.page_number}" if view else slide_id


def _labels(ctx: AnalysisContext, refs: list[EvidenceRef]) -> str:
    seen: list[str] = []
    for r in refs:
        lbl = _slide_label(ctx, r.slide_id)
        if lbl not in seen:
            seen.append(lbl)
    if len(seen) <= 1:
        return "".join(seen)
    return ", ".join(seen[:-1]) + " and " + seen[-1]


def _ref(view: UnitView, sentence: str) -> EvidenceRef:
    return EvidenceRef(slide_id=view.slide_id, excerpt=truncate(sentence, 200))


def _content_sentences(view: UnitView) -> list[str]:
    return view.sentences + view.image_sentences


def _is_footer(view: UnitView, sentence: str, ctx: AnalysisContext) -> bool:
    s = sentence.strip()
    return len(s.split()) < 3 or s.lower().startswith(ctx.team_name.lower())


class HeuristicExtractor(Extractor):
    name = "rule-based-extractor"

    def extract(self, ctx: AnalysisContext) -> ExtractionOutput:
        views = [v for v in ctx.visible_views if v.unit.page_number != 1 or len(ctx.visible_views) == 1]
        topics: list[TopicEvidence] = []
        for topic in S.TOPICS:
            scored: list[tuple[int, UnitView, str]] = []
            for v in views:
                sentences = [s for s in _content_sentences(v) if not _is_footer(v, s, ctx)]
                body_hits = [s for s in sentences if topic.body.search(s)]
                score = (3 if topic.title.search(v.title) else 0) + min(len(body_hits), 2)
                if score >= 3 or len(body_hits) >= 2:
                    excerpt = body_hits[0] if body_hits else (sentences[0] if sentences else "; ".join(v.sentences))
                    excerpt = excerpt or v.title
                    scored.append((score, v, excerpt))
            if not scored and topic.key in WEAK_FALLBACK_TOPICS:
                # Weak signal fallback: a single slide with one relevant sentence.
                for v in views:
                    hit = next((s for s in _content_sentences(v) if topic.body.search(s)), None)
                    if hit and not _is_footer(v, hit, ctx):
                        scored.append((1, v, hit))
                        break
            scored.sort(key=lambda t: (-t[0], t[1].unit.page_number))
            refs = [_ref(v, ex) for _, v, ex in scored[:MAX_REFS_PER_TOPIC] if ex]
            if refs:
                refs.sort(key=lambda r: r.slide_id)
                topics.append(TopicEvidence(topic=topic.key, label=topic.label, evidence=refs))

        claims = self._claims(ctx, views)
        return ExtractionOutput(
            overview=self._overview(ctx, topics),
            target_users=self._target_users(views),
            topics=topics,
            claims=claims,
        )

    def _overview(self, ctx: AnalysisContext, topics: list[TopicEvidence]) -> str:
        first = ctx.visible_views[0] if ctx.visible_views else None
        tagline = ""
        if first:
            candidates = [s for s in first.sentences if len(s.split()) >= 4 and not s.lower().startswith("team")]
            tagline = candidates[0].rstrip(".") if candidates else ""
        product = (first.title if first and first.title else ctx.submission_title).strip()
        parts = []
        if tagline:
            parts.append(f"{ctx.team_name} proposes {product}: {_lower_first(tagline)}.")
        else:
            parts.append(f"{ctx.team_name} proposes {product}.")
        solution = next((t for t in topics if t.topic == "solution"), None)
        if solution and solution.evidence:
            sentence = solution.evidence[0].excerpt.rstrip(".")
            parts.append(f"{sentence}.")
        return " ".join(parts)

    @staticmethod
    def _target_users(views: list[UnitView]) -> str | None:
        for v in views:
            for s in v.sentences:
                if S.TARGET_USER_PATTERN.search(s) and not S.NOVELTY_PATTERN.search(s):
                    return truncate(s, 200)
        return None

    def _claims(self, ctx: AnalysisContext, views: list[UnitView]) -> list[Claim]:
        claims: list[Claim] = []
        for v in views:
            notes_support = bool(S.SUPPORT_PATTERN.search(v.notes))
            for sentence in v.sentences:
                if S.PLAN_PATTERN.search(sentence):
                    continue
                if S.PRICING_PATTERN.search(sentence) and not S.NOVELTY_PATTERN.search(sentence):
                    continue  # pricing is a design choice, not a factual claim
                novelty = bool(S.NOVELTY_PATTERN.search(sentence))
                quant = any(p.search(sentence) for p in S.QUANT_PATTERNS)
                if not (novelty or quant):
                    continue
                if novelty:
                    category = "novelty"
                else:
                    category = next((c for c, p in S.CATEGORY_PATTERNS if p.search(sentence)), "quantitative")
                supported = bool(S.SUPPORT_PATTERN.search(sentence)) or (notes_support and category != "novelty")
                claims.append(
                    Claim(
                        id=f"c{len(claims) + 1}",
                        text=truncate(sentence, 200),
                        category=category,  # type: ignore[arg-type]
                        evidence=[_ref(v, sentence)],
                        supporting_evidence_found=supported,
                    )
                )
        return claims


class HeuristicRubricAnalyzer(RubricAnalyzer):
    name = "rule-based-rubric-analyzer"

    def analyze(self, ctx: AnalysisContext, extraction: ExtractionOutput) -> RubricAnalysisOutput:
        by_topic = {t.topic: t for t in extraction.topics}
        out: list[CriterionAssessment] = []
        for crit in ctx.criteria:
            topic_keys = self._topics_for(crit.name, crit.description)
            refs: list[EvidenceRef] = []
            for key in topic_keys:
                if key in by_topic:
                    refs.extend(by_topic[key].evidence)
            refs = _dedupe(refs)
            issues = self._issues(extraction, topic_keys, refs, by_topic)
            if not refs:
                out.append(
                    CriterionAssessment(
                        criterion_id=crit.id,
                        criterion=crit.name,
                        assessed=False,
                        finding=f"No slide was found that explicitly addresses {crit.name.lower()}.",
                        evidence=[],
                        issues=issues,
                        score=None,
                        not_assessed_reason="No explicit evidence located; the rule-based analyzer does not "
                        "infer a score without evidence.",
                    )
                )
                continue
            slides = {r.slide_id for r in refs}
            has_validation = "validation" in topic_keys and "validation" in by_topic
            specific = sum(1 for r in refs if re.search(r"\d", r.excerpt))
            raw = 4.0 + min(3.0, float(len(slides))) + (1.5 if has_validation else 0.0) + (0.5 if specific else 0.0)
            raw -= sum({"high": 1.0, "medium": 0.6, "low": 0.3}[i.severity] for i in issues)
            raw = max(1.0, min(10.0, raw))
            score = round(raw * ctx.scale_max / 10 * 2) / 2
            finding = (
                f"Relevant content appears on {_labels(ctx, refs)} ({len(refs)} supporting point"
                f"{'s' if len(refs) != 1 else ''} located"
                + (", including validation data" if has_validation else "")
                + ")."
            )
            if issues:
                finding += f" {len(issues)} point{'s' if len(issues) != 1 else ''} need{'s' if len(issues) == 1 else ''} verification."
            out.append(
                CriterionAssessment(
                    criterion_id=crit.id,
                    criterion=crit.name,
                    assessed=True,
                    finding=finding,
                    evidence=refs[:5],
                    issues=issues,
                    score=score,
                )
            )
        return RubricAnalysisOutput(criteria=out)

    @staticmethod
    def _topics_for(name: str, description: str) -> list[str]:
        text = f"{name} {description}"
        keys: list[str] = []
        for pattern, topics in S.CRITERION_HINTS:
            if pattern.search(name):
                keys.extend(t for t in topics if t not in keys)
        if not keys:
            for pattern, topics in S.CRITERION_HINTS:
                if pattern.search(text):
                    keys.extend(t for t in topics if t not in keys)
        return keys

    @staticmethod
    def _issues(extraction: ExtractionOutput, topic_keys: list[str], refs, by_topic) -> list[Issue]:
        issues: list[Issue] = []
        for claim in extraction.claims:
            if claim.supporting_evidence_found:
                continue
            related = set(S.CLAIM_CATEGORY_TO_CRITERIA.get(claim.category, []))
            if related & set(topic_keys):
                issues.append(
                    Issue(
                        type="unsupported_claim",
                        description=f"“{truncate(claim.text, 110)}” — no supporting data or method found.",
                        severity="medium" if claim.category != "novelty" else "low",
                    )
                )
        if "competition" in topic_keys and "competition" not in by_topic:
            issues.append(
                Issue(
                    type="missing_information",
                    description="Existing alternatives and differentiation are not discussed.",
                    severity="medium",
                )
            )
        return issues


class HeuristicVerifier(Verifier):
    name = "rule-based-verifier"

    def verify(
        self, ctx: AnalysisContext, extraction: ExtractionOutput, rubric: RubricAnalysisOutput
    ) -> VerificationOutput:
        items: list[VerifyItem] = []
        views = ctx.visible_views

        def add(**kwargs) -> None:
            items.append(VerifyItem(id=f"v{len(items) + 1}", **kwargs))

        # 1. Unsupported claims
        for claim in extraction.claims:
            if claim.supporting_evidence_found:
                continue
            is_target = bool(S.TARGET_PATTERN.search(claim.text))
            technical = claim.category == "technical"
            headline_number = "%" in claim.text or "$" in claim.text
            if is_target:
                severity = "low"
            elif claim.category in ("impact", "market") and headline_number:
                severity = "high"
            elif claim.category == "business":
                severity = "low"
            else:
                severity = "medium"
            add(
                title=("Stated target: " if is_target else "Claimed: ") + _short_claim(claim.text),
                description=(
                    "This is presented as a goal; no estimate, model or pilot data supporting it was found."
                    if is_target
                    else "No supporting experiment, benchmark, data source or calculation was found in the "
                    "submission for this claim."
                    if claim.category != "novelty"
                    else "Novelty/superlative claim with no comparison to existing work. "
                    "Potential similarity — human verification required."
                ),
                type="feasibility_gap" if technical else "unsupported_claim",
                severity=severity,
                evidence=claim.evidence,
                label="Potential similarity — human verification required." if claim.category == "novelty" else None,
                related_criteria=[],
            )

        # 2. Feasibility dependencies
        pack_text = "\n".join(v.all_text for v in views)
        for key, label, mention, explanation, template in S.DEPENDENCIES:
            hits = [(v, s) for v in views for s in v.sentences if mention.search(s)]
            if not hits or explanation.search(pack_text):
                continue
            what = _describe_dependency(key, hits[0][1])
            add(
                title=f"Technical feasibility: {label}" if key != "integration" else "Dependency on external partners",
                description=template.format(what=what),
                type="feasibility_gap",
                severity="medium" if key != "integration" else "low",
                evidence=[_ref(v, s) for v, s in hits[:2]],
                related_criteria=[],
            )

        # 3. Referenced material that is missing
        has_appendix = any(re.search(r"appendix|annex", v.title, re.I) for v in ctx.views)
        if not has_appendix:
            for v in views:
                s = next((s for s in v.sentences if S.APPENDIX_PATTERN.search(s)), None)
                if s:
                    add(
                        title="Referenced material not included",
                        description=f"{_slide_label(ctx, v.slide_id)} refers to supporting material "
                        "(e.g. an appendix) that is not part of the submitted file.",
                        type="missing_information",
                        severity="medium",
                        evidence=[_ref(v, s)],
                    )
                    break

        # 4. Differentiation
        topics = {t.topic for t in extraction.topics}
        if "competition" not in topics:
            text = " ".join(v.all_text for v in views)
            pattern = next((label for p, label in S.COMMON_PATTERNS if p.search(text)), None)
            solution = next((t for t in extraction.topics if t.topic == "solution"), None)
            add(
                title="Differentiation",
                description=(
                    "The submission does not compare itself with existing alternatives. "
                    + (f"Approaches of this kind ({pattern}) may already exist. " if pattern else
                       "Similar approaches may already exist. ")
                    + "This has not been verified."
                ),
                type="potential_similarity",
                severity="medium",
                evidence=solution.evidence[:1] if solution else [],
                label="Potential similarity — human verification required.",
            )

        # 5. Rubric areas with no evidence
        missing = [c.criterion for c in rubric.criteria if not c.assessed]
        if missing:
            add(
                title="Rubric areas without evidence",
                description="No slide explicitly addresses: " + ", ".join(missing)
                + ". Check whether the information is present in a form the system could not read.",
                type="missing_information",
                severity="medium" if len(missing) > 1 else "low",
                evidence=[],
                related_criteria=missing,
            )

        order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda i: (order[i.severity], int(i.id[1:])))
        return VerificationOutput(items=items[:MAX_VERIFY_ITEMS])


class HeuristicBriefWriter(BriefWriter):
    name = "rule-based-brief-writer"

    STRENGTH_RULES: list[tuple[str, str, str | None]] = [
        # (topic, text, extra requirement regex on excerpt)
        ("problem", "Explicit problem statement backed by specific data", r"\d|survey|report|data"),
        ("problem", "Explicit problem statement", None),
        ("target_users", "Clearly defined target users", None),
        ("validation", "Includes validation evidence (tests, benchmarks or user research)", None),
        ("architecture", "Concrete technical approach / implementation workflow described", None),
        ("competition", "Positions the solution against existing alternatives", None),
        ("plan", "Phased implementation plan with milestones", None),
        ("business", "Revenue model or unit economics stated", None),
        ("scalability", "Describes a concrete path to scale", None),
    ]

    def write(self, ctx, extraction, rubric, verification) -> BriefWriterOutput:
        by_topic = {t.topic: t for t in extraction.topics}
        strengths: list[Strength] = []
        used_topics: set[str] = set()
        for topic, text, extra in self.STRENGTH_RULES:
            if topic in used_topics or topic not in by_topic:
                continue
            refs = by_topic[topic].evidence
            if extra:
                refs = [r for r in refs if re.search(extra, r.excerpt, re.I)]
                if not refs:
                    continue
            if topic == "validation" and not any(c.supporting_evidence_found for c in extraction.claims):
                if not any(S.SUPPORT_PATTERN.search(r.excerpt) for r in refs):
                    continue
            used_topics.add(topic)
            strengths.append(Strength(id=f"s{len(strengths) + 1}", text=text, evidence=refs[:2]))
        return BriefWriterOutput(
            overview=extraction.overview,
            strengths=strengths[:6],
            verify_order=[i.id for i in verification.items][:6],
        )


def _dedupe(refs: list[EvidenceRef]) -> list[EvidenceRef]:
    seen, out = set(), []
    for r in refs:
        key = (r.slide_id, r.excerpt)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return sorted(out, key=lambda r: r.slide_id)


def _short_claim(text: str) -> str:
    text = text.strip().rstrip(".")
    text = re.sub(r"^(goal|target|aim|objective)s?\s*:\s*", "", text, flags=re.I)
    return truncate(text, 70)


def _lower_first(text: str) -> str:
    """Lower-case the first letter unless the first word looks like an acronym or name."""
    word = text.split(" ", 1)[0]
    if len(word) > 1 and word[1:].islower() and "-" not in word[:3]:
        return text[0].lower() + text[1:]
    return text


def _describe_dependency(key: str, sentence: str) -> str:
    if key == "hardware":
        m = re.search(r"([\w-]+\s+)?(sensors?|devices?|hardware|buoy|modem|drones?)", sentence, re.I)
        return m.group(0).strip().lower() if m else "custom hardware"
    return "“" + truncate(sentence.rstrip("."), 90) + "”"

