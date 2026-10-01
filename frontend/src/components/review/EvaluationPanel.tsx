import clsx from "clsx";
import { ArrowRight, Bot, CheckCircle2, ChevronDown, EyeOff, Info, Lock, MessageSquarePlus, Scale, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { DIRECTION_LABEL, RECOMMENDATION_LABEL, formatDateTime, formatScore, slideLabel } from "../../lib/format";
import type { AIAssessment, Criterion, CriterionScore, Evaluation, ReviewPayload } from "../../lib/types";
import { Badge, Button, Callout, Dialog, ScorePicker } from "../ui";
import type { ViewSlide } from "./JudgeBriefPanel";

type Recommendation = NonNullable<Evaluation["recommendation"]>;

interface Draft {
  scores: Record<number, number>;
  comments: Record<number, string>;
  overall: string;
  recommendation: Recommendation | null;
}

export interface SubmitBody {
  criterion_scores: CriterionScore[];
  overall_comment: string;
  recommendation: Recommendation | null;
}

export interface FinalizeBody {
  decision: "keep" | "revise";
  revised_scores?: CriterionScore[];
  reason: string;
}

function weighted(criteria: Criterion[], scores: Record<number, number>, max: number): number | null {
  if (criteria.some((c) => scores[c.id] === undefined)) return null;
  const total = criteria.reduce((s, c) => s + c.weight, 0) || 1;
  return Math.round((1000 * criteria.reduce((s, c) => s + c.weight * (scores[c.id] / max), 0)) / total) / 10;
}

const draftKey = (id: number) => `evidra.draft.${id}`;

function loadDraft(id: number): Draft {
  try {
    const raw = localStorage.getItem(draftKey(id));
    if (raw) return JSON.parse(raw) as Draft;
  } catch {
    /* ignore */
  }
  return { scores: {}, comments: {}, overall: "", recommendation: null };
}

export function EvaluationPanel({
  payload,
  onSubmit,
  onReveal,
  onFinalize,
  onViewSlide,
  onDraftChange,
}: {
  payload: ReviewPayload;
  onSubmit: (b: SubmitBody) => Promise<void>;
  onReveal: () => Promise<void>;
  onFinalize: (b: FinalizeBody) => Promise<void>;
  onViewSlide: ViewSlide;
  /** Reports whether the judge has started scoring (drives the step indicator). */
  onDraftChange?: (hasScores: boolean) => void;
}) {
  const { evaluation, reveal, revision, round } = payload;
  if (revision && evaluation) return <CompletedView payload={payload} />;
  if (evaluation && reveal) return <RevealView payload={payload} onFinalize={onFinalize} onViewSlide={onViewSlide} />;
  if (evaluation) return <SubmittedView evaluation={evaluation} onReveal={onReveal} />;
  return (
    <ScoringForm
      assignmentId={payload.assignment.id}
      criteria={round.criteria}
      max={round.score_scale_max}
      onSubmit={onSubmit}
      onDraftChange={onDraftChange}
    />
  );
}

// ---------------------------------------------------------------------------
// 1. Independent scoring
// ---------------------------------------------------------------------------

function ScoringForm({
  assignmentId,
  criteria,
  max,
  onSubmit,
  onDraftChange,
}: {
  assignmentId: number;
  criteria: Criterion[];
  max: number;
  onSubmit: (b: SubmitBody) => Promise<void>;
  onDraftChange?: (hasScores: boolean) => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => loadDraft(assignmentId));
  const [openNotes, setOpenNotes] = useState<Record<number, boolean>>({});
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(draftKey(assignmentId), JSON.stringify(draft));
    } catch {
      /* ignore */
    }
  }, [assignmentId, draft]);

  const hasScores = Object.keys(draft.scores).length > 0;
  useEffect(() => onDraftChange?.(hasScores), [hasScores, onDraftChange]);

  const total = weighted(criteria, draft.scores, max);
  const scored = criteria.filter((c) => draft.scores[c.id] !== undefined).length;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        criterion_scores: criteria.map((c) => ({ criterion_id: c.id, score: draft.scores[c.id], comment: draft.comments[c.id] ?? "" })),
        overall_comment: draft.overall,
        recommendation: draft.recommendation,
      });
      localStorage.removeItem(draftKey(assignmentId));
      setConfirm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="scroll-thin min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        <div className="flex items-start gap-2.5 rounded-lg border border-line bg-canvas px-3 py-2.5">
          <EyeOff className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <div className="text-[12.5px] leading-relaxed text-ink-2">
            <span className="font-semibold text-ink">AI score hidden.</span> Score independently first. The AI's preliminary assessment is revealed only
            after you submit.
          </div>
        </div>

        {criteria.map((c, i) => (
          <div key={c.id} className="rounded-xl border border-line bg-surface p-3.5 shadow-card">
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <div className="min-w-0">
                <div className="text-[13.5px] font-semibold text-ink">
                  <span className="tabular mr-1.5 text-faint">{i + 1}.</span>
                  {c.name}
                </div>
                {c.description && <p className="mt-0.5 text-[12px] leading-snug text-muted">{c.description}</p>}
              </div>
              <span className="tabular shrink-0 rounded bg-sunken px-1.5 py-0.5 text-[11.5px] font-medium text-muted">{c.weight}%</span>
            </div>
            <ScorePicker max={max} value={draft.scores[c.id] ?? null} onChange={(v) => setDraft((d) => ({ ...d, scores: { ...d.scores, [c.id]: v } }))} />
            {openNotes[c.id] || draft.comments[c.id] ? (
              <textarea
                className="input mt-2 min-h-[56px] resize-y text-[13px]"
                placeholder={`Notes on ${c.name.toLowerCase()} (optional)`}
                value={draft.comments[c.id] ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, comments: { ...d.comments, [c.id]: e.target.value } }))}
              />
            ) : (
              <button onClick={() => setOpenNotes((o) => ({ ...o, [c.id]: true }))} className="mt-2 inline-flex items-center gap-1 text-[12px] text-muted hover:text-ink">
                <MessageSquarePlus className="h-3.5 w-3.5" /> Add note
              </button>
            )}
          </div>
        ))}

        <div>
          <label className="label">Overall assessment</label>
          <textarea
            className="input min-h-[88px] resize-y text-[13px]"
            placeholder="Your summary for the organizer (optional)"
            value={draft.overall}
            onChange={(e) => setDraft((d) => ({ ...d, overall: e.target.value }))}
          />
        </div>
        <div>
          <label className="label">Recommendation</label>
          <div className="grid grid-cols-3 gap-1.5">
            {(["advance", "discuss", "do_not_advance"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setDraft((d) => ({ ...d, recommendation: d.recommendation === r ? null : r }))}
                className={clsx(
                  "h-8 rounded-md border text-[12.5px] font-medium transition-colors",
                  draft.recommendation === r ? "border-navy bg-navy text-white" : "border-line bg-surface text-ink-2 hover:bg-sunken",
                )}
              >
                {RECOMMENDATION_LABEL[r]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-line bg-surface p-4">
        <div className="mb-3 flex items-end justify-between">
          <div>
            <div className="text-[12px] text-muted">Your weighted score</div>
            <div className="tabular text-[24px] font-semibold leading-tight text-ink">
              {total === null ? <span className="text-faint">—</span> : formatScore(total)}
              <span className="text-[13px] font-normal text-faint"> / 100</span>
            </div>
          </div>
          <div className="text-right text-[12px] text-muted">
            {scored}/{criteria.length} criteria scored
          </div>
        </div>
        {error && <Callout tone="danger" className="mb-3">{error}</Callout>}
        <Button variant="primary" size="lg" className="w-full" disabled={total === null} onClick={() => setConfirm(true)}>
          Submit evaluation
        </Button>
      </div>

      <Dialog
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Submit your independent evaluation?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Keep editing
            </Button>
            <Button variant="primary" loading={busy} onClick={submit}>
              Submit and reveal AI assessment
            </Button>
          </>
        }
      >
        <p className="text-[13.5px] leading-relaxed text-ink-2">
          Your scores ({total !== null ? `${formatScore(total)} / 100` : "—"}) will be recorded as your independent evaluation and can't be edited. You'll then
          see the AI's preliminary assessment and can keep your score or record a revision with a reason.
        </p>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Submitted, awaiting reveal
// ---------------------------------------------------------------------------

function SubmittedView({ evaluation, onReveal }: { evaluation: Evaluation; onReveal: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="space-y-4 p-4">
      <Callout tone="ok" title="Independent evaluation recorded">
        Submitted {formatDateTime(evaluation.submitted_at)} with a weighted score of {formatScore(evaluation.weighted_score)} / 100.
      </Callout>
      <div className="rounded-xl border border-line bg-surface p-4 text-center shadow-card">
        <Bot className="mx-auto h-6 w-6 text-muted" />
        <div className="mt-2 text-[14px] font-semibold">Compare with the AI assessment</div>
        <p className="mx-auto mt-1 max-w-xs text-[12.5px] text-muted">The AI assessment is preliminary and is not a decision. Your evaluation remains authoritative.</p>
        <Button
          variant="primary"
          className="mt-3"
          loading={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onReveal();
            } finally {
              setBusy(false);
            }
          }}
        >
          Reveal AI assessment
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Reveal + keep / revise
// ---------------------------------------------------------------------------

function RevealView({ payload, onFinalize, onViewSlide }: { payload: ReviewPayload; onFinalize: (b: FinalizeBody) => Promise<void>; onViewSlide: ViewSlide }) {
  const { evaluation, reveal, round } = payload;
  const criteria = round.criteria;
  const max = round.score_scale_max;
  const initial = useMemo(() => Object.fromEntries(evaluation!.criterion_scores.map((s) => [s.criterion_id, s.score])), [evaluation]);
  const [mode, setMode] = useState<"compare" | "revise">("compare");
  const [revised, setRevised] = useState<Record<number, number>>(initial);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<"keep" | "revise" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const assessment: AIAssessment | undefined = reveal?.assessment;
  const aiByCriterion = new Map(assessment?.criteria.map((c) => [c.criterion_id, c]) ?? []);
  const revisedTotal = weighted(criteria, revised, max);
  const changed = criteria.some((c) => revised[c.id] !== initial[c.id]);

  async function finalize(decision: "keep" | "revise") {
    setBusy(decision);
    setError(null);
    try {
      await onFinalize({
        decision,
        reason,
        revised_scores:
          decision === "revise"
            ? criteria.map((c) => ({ criterion_id: c.id, score: revised[c.id], comment: evaluation!.criterion_scores.find((s) => s.criterion_id === c.id)?.comment ?? "" }))
            : undefined,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="scroll-thin min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {!reveal?.ai_available || !assessment ? (
          <Callout tone="warn" title="AI analysis unavailable. Human review can continue.">
            There is no AI assessment to compare with. Your submitted evaluation stands; confirm it to finish.
          </Callout>
        ) : (
          <>
            <div className="animate-slide-up rounded-xl border border-line-strong bg-surface shadow-card">
              <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
                <Sparkles className="h-4 w-4 text-accent" />
                <span className="text-[13px] font-semibold text-ink">Evidra's preliminary assessment</span>
              </div>
              <div className="px-4 py-3">
                <div className="flex items-start gap-2 rounded-md border border-[#d6e0fb] bg-accent-soft px-2.5 py-2 text-[12.5px] text-accent-strong">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>
                    <span className="font-semibold">{assessment.label}</span> Your independent evaluation remains the decision of record.
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <ScoreBox label="Your score" value={evaluation!.weighted_score} strong />
                  <ScoreBox label="AI preliminary" value={assessment.overall_score} />
                  <DiffBox value={assessment.overall_score === null ? null : assessment.overall_score - evaluation!.weighted_score} />
                </div>
                <p className="mt-1.5 text-[11.5px] text-faint">Weighted scores out of 100 · difference = AI − yours</p>
                {assessment.assessed_weight < 100 && (
                  <p className="mt-1.5 text-[12px] text-warn">
                    The AI could assess only {formatScore(assessment.assessed_weight)}% of the rubric weight; its score covers assessed criteria only.
                  </p>
                )}
                <p className="mt-1.5 text-[11.5px] text-faint">
                  Engine: {assessment.engine === "rule-based" ? "offline rule-based analyzer" : assessment.model ?? assessment.engine}
                </p>
              </div>
            </div>

            <div className="space-y-2">
              {criteria.map((c) => {
                const ai = aiByCriterion.get(c.id);
                return (
                  <CriterionCompare
                    key={c.id}
                    name={c.name}
                    weight={c.weight}
                    mine={initial[c.id]}
                    revisedValue={mode === "revise" ? revised[c.id] : undefined}
                    ai={ai?.assessed ? ai.score : null}
                    max={max}
                    finding={ai?.finding}
                    notAssessedReason={ai && !ai.assessed ? ai.not_assessed_reason ?? "Not assessed" : null}
                    issues={ai?.issues ?? []}
                    evidence={ai?.evidence ?? []}
                    onViewSlide={onViewSlide}
                    editor={
                      mode === "revise" ? (
                        <ScorePicker max={max} value={revised[c.id]} compareValue={ai?.assessed ? ai.score : null} onChange={(v) => setRevised((r) => ({ ...r, [c.id]: v }))} />
                      ) : null
                    }
                  />
                );
              })}
            </div>
          </>
        )}

        {mode === "revise" && (
          <div className="animate-slide-up">
            <label className="label">Why are you changing your score? (optional)</label>
            <textarea
              className="input min-h-[76px] resize-y text-[13px]"
              placeholder="e.g. I missed that the impact figures have no supporting data on slide 7."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <p className="mt-1 text-[11.5px] text-faint">Your original score, the AI score and your revision are all recorded. The blue dot marks the AI's criterion score.</p>
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-line bg-surface p-4">
        {error && <Callout tone="danger" className="mb-3">{error}</Callout>}
        {mode === "compare" ? (
          <div className="grid grid-cols-2 gap-2">
            <Button variant="primary" loading={busy === "keep"} onClick={() => finalize("keep")}>
              Keep my score
            </Button>
            <Button variant="secondary" onClick={() => setMode("revise")}>
              Revise my score
            </Button>
          </div>
        ) : (
          <>
            <div className="tabular mb-3 flex items-baseline justify-between text-[13px]">
              <span className="text-muted">Revised weighted score</span>
              <span>
                <span className="text-faint line-through">{formatScore(evaluation!.weighted_score)}</span>
                <ArrowRight className="mx-1 inline h-3 w-3 text-faint" />
                <span className="text-[18px] font-semibold text-ink">{formatScore(revisedTotal)}</span>
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="ghost"
                onClick={() => {
                  setMode("compare");
                  setRevised(initial);
                }}
              >
                Cancel
              </Button>
              <Button variant="primary" loading={busy === "revise"} disabled={!changed} onClick={() => finalize("revise")}>
                Save revised score
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function formatSigned(v: number): string {
  const r = Math.round(v * 10) / 10;
  return r > 0 ? `+${formatScore(r)}` : r < 0 ? `−${formatScore(-r)}` : "0";
}

function DiffBox({ value }: { value: number | null }) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong px-2.5 py-2" title="AI preliminary minus your score">
      <div className="whitespace-nowrap text-[11px] text-muted">Difference</div>
      <div className="tabular text-[20px] font-semibold leading-tight text-ink-2">{value === null ? "—" : formatSigned(value)}</div>
    </div>
  );
}

function ScoreBox({ label, value, strong }: { label: string; value: number | null | undefined; strong?: boolean }) {
  return (
    <div className={clsx("rounded-lg border px-2.5 py-2", strong ? "border-navy/20 bg-navy/[0.03]" : "border-line")}>
      <div className="whitespace-nowrap text-[11px] text-muted">{label}</div>
      <div className="tabular text-[20px] font-semibold leading-tight">{formatScore(value)}</div>
    </div>
  );
}

function CriterionCompare({
  name,
  weight,
  mine,
  revisedValue,
  ai,
  max,
  finding,
  notAssessedReason,
  issues,
  evidence,
  onViewSlide,
  editor,
}: {
  name: string;
  weight: number;
  mine: number;
  revisedValue?: number;
  ai: number | null;
  max: number;
  finding?: string;
  notAssessedReason: string | null;
  issues: { description: string; severity: string }[];
  evidence: { slide_id: string; excerpt: string; page_number: number | null }[];
  onViewSlide: ViewSlide;
  editor: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-line bg-surface">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium text-ink">{name}</div>
          <div className="text-[11px] text-faint">{weight}% weight</div>
        </div>
        <div className="tabular flex items-center gap-3 text-[13px]">
          <span title="Your score">
            <span className="text-[10.5px] text-faint">You </span>
            <span className="font-semibold">{revisedValue !== undefined && revisedValue !== mine ? <><s className="text-faint">{mine}</s> {revisedValue}</> : mine}</span>
          </span>
          <span title="AI preliminary score">
            <span className="text-[10.5px] text-faint">AI </span>
            {ai === null ? <Badge>Not assessed</Badge> : <span className="font-semibold text-accent-strong">{formatScore(ai)}</span>}
          </span>
          <span className="text-[10.5px] text-faint">/{max}</span>
        </div>
        <ChevronDown className={clsx("h-4 w-4 shrink-0 text-faint transition-transform", open && "rotate-180")} />
      </button>
      {editor && <div className="px-3 pb-3">{editor}</div>}
      {open && (
        <div className="animate-fade-in space-y-2 border-t border-line px-3 py-2.5 text-[12.5px]">
          {notAssessedReason ? <p className="text-muted">{notAssessedReason}</p> : <p className="leading-relaxed text-ink-2">{finding}</p>}
          {issues.length > 0 && (
            <ul className="space-y-1">
              {issues.map((i, k) => (
                <li key={k} className="text-muted">
                  • {i.description}
                </li>
              ))}
            </ul>
          )}
          {evidence.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {[...new Map(evidence.map((e) => [e.slide_id, e])).values()].map((e) => (
                <button key={e.slide_id} onClick={() => onViewSlide(e.slide_id, e.excerpt)} className="font-medium text-accent hover:underline">
                  View {slideLabel(e.slide_id, e.page_number)}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. Completed
// ---------------------------------------------------------------------------

function CompletedView({ payload }: { payload: ReviewPayload }) {
  const r = payload.revision!;
  const e = payload.evaluation!;
  const criteria = payload.round.criteria;
  return (
    <div className="scroll-thin h-full space-y-4 overflow-y-auto p-4">
      <div className="rounded-xl border border-[#c9ead8] bg-ok-soft px-4 py-3">
        <div className="flex items-center gap-2 text-[14px] font-semibold text-ok">
          <CheckCircle2 className="h-4 w-4" /> Final evaluation recorded
        </div>
        <p className="mt-0.5 text-[12.5px] text-[#0b5535]">
          {r.decision === "revised" ? "You revised your score after reviewing the AI assessment." : "You kept your independent score."}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <MiniScore label="Initial (yours)" value={r.human_initial_score} />
        <MiniScore label="AI preliminary" value={r.ai_score} muted />
        <MiniScore label="Final (yours)" value={r.human_revised_score} strong />
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={r.decision === "revised" ? "accent" : "neutral"} icon={<Scale className="h-3 w-3" />}>
          {r.decision === "revised" ? `Revised ${formatSigned(r.initial_to_revised_difference)} points` : "Kept initial score"}
        </Badge>
        {r.decision === "revised" && <Badge>{DIRECTION_LABEL[r.revision_direction]}</Badge>}
        {e.recommendation && <Badge tone="navy">{RECOMMENDATION_LABEL[e.recommendation]}</Badge>}
      </div>
      <dl className="tabular grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[12px] text-muted">
        <dt>Submitted</dt>
        <dd className="text-ink-2">{formatDateTime(e.submitted_at)}</dd>
        <dt>AI revealed</dt>
        <dd className="text-ink-2">{formatDateTime(payload.reveal?.revealed_at)}</dd>
        <dt>Finalized</dt>
        <dd className="text-ink-2">{formatDateTime(payload.assignment.completed_at)}</dd>
      </dl>
      {r.revision_reason && (
        <div className="rounded-lg border border-line bg-surface px-3 py-2.5 text-[13px]">
          <div className="eyebrow mb-1">Reason for revision</div>
          <p className="text-ink-2">{r.revision_reason}</p>
        </div>
      )}

      <div className="rounded-xl border border-line bg-surface">
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-faint">
              <th className="px-3 py-2 font-medium">Criterion</th>
              <th className="px-2 py-2 text-right font-medium">Initial</th>
              <th className="px-3 py-2 text-right font-medium">Final</th>
            </tr>
          </thead>
          <tbody>
            {criteria.map((c) => {
              const i = r.initial_criterion_scores.find((s) => s.criterion_id === c.id)?.score;
              const f = r.revised_criterion_scores.find((s) => s.criterion_id === c.id)?.score;
              return (
                <tr key={c.id} className="border-b border-line last:border-0">
                  <td className="px-3 py-2 text-ink-2">{c.name}</td>
                  <td className="tabular px-2 py-2 text-right text-muted">{i}</td>
                  <td className={clsx("tabular px-3 py-2 text-right font-semibold", f !== i && "text-accent-strong")}>{f}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {e.overall_comment && (
        <div className="rounded-lg border border-line bg-surface px-3 py-2.5 text-[13px]">
          <div className="eyebrow mb-1">Your overall assessment</div>
          <p className="whitespace-pre-wrap text-ink-2">{e.overall_comment}</p>
        </div>
      )}
      <p className="flex items-center gap-1.5 text-[11.5px] text-faint">
        <Lock className="h-3 w-3" /> Initial score, AI preliminary assessment, final score and reason are recorded in the audit trail.
      </p>
    </div>
  );
}

function MiniScore({ label, value, strong, muted }: { label: string; value: number | null; strong?: boolean; muted?: boolean }) {
  return (
    <div className={clsx("rounded-lg border px-2.5 py-2", strong ? "border-navy/25 bg-surface" : "border-line bg-surface")}>
      <div className="text-[11px] text-muted">{label}</div>
      <div className={clsx("tabular text-[19px] font-semibold", muted && "text-accent-strong")}>{formatScore(value)}</div>
    </div>
  );
}
