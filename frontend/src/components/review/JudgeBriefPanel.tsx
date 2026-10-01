import clsx from "clsx";
import {
  AlertTriangle,
  Check,
  CircleHelp,
  CircleSlash,
  FileSearch,
  Info,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { INTEGRITY_LABEL, SEVERITY_LABEL, VERIFY_TYPE_LABEL, slideLabel } from "../../lib/format";
import type {
  AnalysisInfo,
  EvidenceRef,
  FindingResponse,
  IntegrityReport,
  NotAssessedItem,
  Severity,
  VerifyItem,
} from "../../lib/types";
import { Badge, Callout, integrityTone } from "../ui";

export type ViewSlide = (slideId: string, excerpt?: string) => void;
export type RespondFn = (key: string, response: FindingResponse["response"], note: string) => Promise<void>;

interface Props {
  analysis: AnalysisInfo;
  integrity: IntegrityReport | null;
  notAssessed: NotAssessedItem[];
  documentMessage?: string | null;
  onViewSlide: ViewSlide;
  responses?: Record<string, FindingResponse>;
  onRespond?: RespondFn;
  readOnly?: boolean;
}

export function JudgeBriefPanel({ analysis, integrity, notAssessed, documentMessage, onViewSlide, responses = {}, onRespond, readOnly }: Props) {
  const brief = analysis.brief;
  const respond = readOnly ? undefined : onRespond;
  // A document that could not be processed never gets an AI analysis.
  const docFailed = Boolean(documentMessage);
  const aiUnavailable = analysis.status === "failed" || (docFailed && analysis.status !== "completed");

  return (
    <div className="space-y-5">
      {documentMessage && <Callout tone="danger" title={documentMessage} />}

      {aiUnavailable && (
        <Callout tone="warn" title="AI analysis unavailable. Human review can continue.">
          {docFailed
            ? "No AI findings were produced because the document could not be processed. Please review the original file."
            : "The original submission, integrity check and processing notes remain available. No AI findings are shown because none could be produced reliably."}
        </Callout>
      )}
      {!aiUnavailable && (analysis.status === "pending" || analysis.status === "running") && (
        <Callout tone="accent" icon={<Loader2 className="h-4 w-4 animate-spin" />} title="Preparing the judge brief…">
          You can already review the original document.
        </Callout>
      )}

      {brief && (
        <p id="overview" className="px-1 text-[13.5px] leading-relaxed text-ink-2">
          <span className="font-semibold text-ink">Overview · </span>
          {brief.overview}
          {brief.target_users && <span className="text-muted"> Stated users: {brief.target_users}</span>}
        </p>
      )}

      {brief && <VerifySection items={brief.verify_these} onViewSlide={onViewSlide} responses={responses} onRespond={respond} readOnly={readOnly} />}

      {brief && (
        <Section id="strengths" icon={<Sparkles className="h-4 w-4" />} title="Strengths" subtitle="Evidence-backed positives, each linked to its source">
          {brief.strengths.length === 0 ? (
            <p className="text-[13px] text-muted">No evidence-backed strengths were identified.</p>
          ) : (
            <ul className="space-y-2">
              {brief.strengths.map((s) => (
                <li key={s.id} className="rounded-lg border border-line bg-surface px-3 py-2.5">
                  <div className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
                    <div className="min-w-0 flex-1">
                      <div className="text-[13.5px] font-medium text-ink">{s.text}</div>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {s.evidence.map((e, i) => (
                          <SlideChip key={i} ev={e} onViewSlide={onViewSlide} />
                        ))}
                      </div>
                    </div>
                  </div>
                  {respond && <FindingControls findingKey={`strength:${s.id}`} value={responses[`strength:${s.id}`]} onRespond={respond} compact />}
                  {readOnly && responses[`strength:${s.id}`] && <ResponseBadge r={responses[`strength:${s.id}`]} />}
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      <Section
        id="not-assessed"
        icon={<CircleSlash className="h-4 w-4" />}
        title="Not assessed"
        subtitle="Material Evidra could not reliably evaluate — not a judgment of the submission"
      >
        {docFailed ? (
          <p className="text-[13px] text-ink-2">
            Not assessed — insufficient accessible evidence. The document could not be processed, so none of its content was evaluated by Evidra.
          </p>
        ) : notAssessed.length === 0 ? (
          <p className="text-[13px] text-muted">
            Nothing flagged. Image-only content, inaccessible external material, embedded media and rendering problems are listed here when present.
          </p>
        ) : (
          <>
            <p className="mb-2.5 text-[12.5px] text-muted">
              Not assessed — insufficient accessible evidence. Please review these parts of the original yourself.
            </p>
            <ul className="space-y-2">
              {notAssessed.map((n, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px]">
                  <CircleHelp className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint" />
                  <span className="text-ink-2">
                    <span className="font-medium text-ink">{n.area.charAt(0).toUpperCase() + n.area.slice(1)}.</span> {n.reason}
                    {n.slide_id && (
                      <button onClick={() => onViewSlide(n.slide_id!)} className="ml-1.5 whitespace-nowrap font-medium text-accent hover:underline">
                        → View {slideLabel(n.slide_id)}
                      </button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <IntegritySection integrity={integrity} onViewSlide={onViewSlide} />

      {brief && brief.evidence_highlights.length > 0 && (
        <Section id="evidence" icon={<FileSearch className="h-4 w-4" />} title="Evidence map" subtitle="Where the key elements of the proposal appear">
          <ul className="divide-y divide-line">
            {brief.evidence_highlights.map((h) => (
              <li key={h.id} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
                <div className="w-[132px] shrink-0 pt-0.5 text-[13px] font-medium text-ink">{h.label}</div>
                <div className="min-w-0 flex-1 space-y-1.5">
                  {h.evidence.map((e, i) => (
                    <EvidenceLine key={i} ev={e} onViewSlide={onViewSlide} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {brief && brief.rubric_coverage.length > 0 && (
        <Section id="rubric" icon={<Info className="h-4 w-4" />} title="Rubric map" subtitle="Where each criterion is addressed — no scores before you submit">
          <ul className="divide-y divide-line">
            {brief.rubric_coverage.map((c) => (
              <li key={c.criterion_id} className="flex items-start gap-3 py-2 first:pt-0 last:pb-0">
                <div className="w-[150px] shrink-0 text-[13px] font-medium text-ink">{c.criterion}</div>
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                  {c.coverage === "not_found" ? (
                    <span className="text-[12.5px] text-muted">Not assessed — no explicit evidence located</span>
                  ) : (
                    uniqueSlides(c.evidence).map((e) => <SlideChip key={e.slide_id} ev={e} onViewSlide={onViewSlide} />)
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {brief && (
        <p className="px-1 pb-2 text-[11.5px] leading-relaxed text-faint">
          Prepared by {brief.provenance.engine === "rule-based" ? "Evidra's offline rule-based analyzer" : brief.provenance.model ?? brief.provenance.engine}. {brief.provenance.note} This brief supports — and does not replace — your
          own reading of the submission.
        </p>
      )}
    </div>
  );
}

function uniqueSlides(refs: EvidenceRef[]): EvidenceRef[] {
  const seen = new Set<string>();
  return refs.filter((r) => (seen.has(r.slide_id) ? false : (seen.add(r.slide_id), true)));
}

const PRIORITY_ORDER: Severity[] = ["high", "medium", "low"];
const PRIORITY_STYLE: Record<Severity, string> = {
  high: "bg-navy text-white",
  medium: "bg-accent-soft text-accent-strong ring-1 ring-inset ring-[#d6e0fb]",
  low: "bg-sunken text-ink-2 ring-1 ring-inset ring-line",
};

/** The centerpiece of the brief: source-linked findings that deserve human attention. */
function VerifySection({
  items,
  onViewSlide,
  responses,
  onRespond,
  readOnly,
}: {
  items: VerifyItem[];
  onViewSlide: ViewSlide;
  responses: Record<string, FindingResponse>;
  onRespond?: RespondFn;
  readOnly?: boolean;
}) {
  const high = items.filter((v) => v.severity === "high").length;
  const groups = PRIORITY_ORDER.map((p) => ({ priority: p, items: items.filter((v) => v.severity === p) })).filter((g) => g.items.length);
  let n = 0;
  return (
    <section id="verify" className="scroll-mt-4 overflow-hidden rounded-xl border-2 border-navy/80 bg-surface shadow-card">
      <div className="flex items-start justify-between gap-3 border-b border-line bg-navy/[0.04] px-4 py-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-[15px] font-semibold uppercase tracking-wide text-navy">
            <AlertTriangle className="h-4 w-4" /> Verify these
          </h3>
          <p className="mt-0.5 text-[12.5px] text-ink-2">Source-linked findings that deserve your attention before you score.</p>
        </div>
        <div className="shrink-0 text-right">
          <div className="tabular text-[13px] font-semibold text-ink">
            {items.length} evidence check{items.length === 1 ? "" : "s"}
          </div>
          {high > 0 && <div className="tabular text-[12px] text-muted">{high} high priority</div>}
        </div>
      </div>
      <div className="p-4">
        {items.length === 0 ? (
          <p className="text-[13px] text-muted">No specific evidence checks were generated. This does not mean the submission has no issues.</p>
        ) : (
          <div className="space-y-4">
            {groups.map((g) => (
              <div key={g.priority}>
                <div className="mb-2 flex items-center gap-2">
                  <span className={clsx("rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide", PRIORITY_STYLE[g.priority])}>
                    {SEVERITY_LABEL[g.priority]}
                  </span>
                  <span className="h-px flex-1 bg-line" />
                </div>
                <ol className="space-y-2.5">
                  {g.items.map((v) => (
                    <VerifyCard
                      key={v.id}
                      index={++n}
                      item={v}
                      onViewSlide={onViewSlide}
                      response={responses[`verify:${v.id}`]}
                      onRespond={onRespond}
                      readOnly={readOnly}
                    />
                  ))}
                </ol>
              </div>
            ))}
            <p className="text-[11.5px] text-faint">
              Priority reflects how much human attention a finding deserves, not how good or bad the submission is. Agree, disagree or mark
              unsure on any finding.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function Section({ id, icon, title, subtitle, children, accent }: { id: string; icon: ReactNode; title: string; subtitle?: string; children: ReactNode; accent?: boolean }) {
  return (
    <section id={id} className="scroll-mt-4">
      <div className="mb-2">
        <div className="flex items-center gap-2">
          <span className={clsx(accent ? "text-navy" : "text-muted")}>{icon}</span>
          <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
        </div>
        {subtitle && <p className="mt-0.5 pl-6 text-[12px] leading-snug text-muted">{subtitle}</p>}
      </div>
      <div className={clsx("rounded-xl border bg-surface p-4 shadow-card", accent ? "border-line-strong" : "border-line")}>{children}</div>
    </section>
  );
}

export function SlideChip({ ev, onViewSlide }: { ev: EvidenceRef; onViewSlide: ViewSlide }) {
  return (
    <button
      onClick={() => onViewSlide(ev.slide_id, ev.excerpt)}
      className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md border border-[#d6e0fb] bg-accent-soft px-1.5 py-0.5 text-[12px] font-medium text-accent-strong transition-colors hover:border-accent hover:bg-[#e2e9fc]"
      title={ev.excerpt}
    >
      View {slideLabel(ev.slide_id, ev.page_number)}
    </button>
  );
}

function EvidenceLine({ ev, onViewSlide }: { ev: EvidenceRef; onViewSlide: ViewSlide }) {
  return (
    <div className="flex items-start gap-2">
      <SlideChip ev={ev} onViewSlide={onViewSlide} />
      <span className="min-w-0 pt-0.5 text-[12.5px] leading-snug text-muted">
        “{ev.excerpt}”
        {ev.via === "ocr" && <span className="ml-1 text-faint">(read from image)</span>}
        {ev.via === "speaker_notes" && <span className="ml-1 text-faint">(speaker notes)</span>}
        {!ev.verified && <span className="ml-1 text-warn">(excerpt not matched verbatim)</span>}
      </span>
    </div>
  );
}

function VerifyCard({ index, item, onViewSlide, response, onRespond, readOnly }: { index: number; item: VerifyItem; onViewSlide: ViewSlide; response?: FindingResponse; onRespond?: RespondFn; readOnly?: boolean }) {
  return (
    <li className={clsx("rounded-lg border bg-surface px-3.5 py-3", item.type === "integrity" ? "border-danger-line bg-danger-soft/40" : "border-line")}>
      <div className="flex items-start gap-3">
        <span className="tabular mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-navy text-[11px] font-semibold text-white">{index}</span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
            <span className="text-[13.5px] font-semibold text-ink">{item.title}</span>
            <Badge tone={item.type === "integrity" ? "danger" : "neutral"}>{VERIFY_TYPE_LABEL[item.type]}</Badge>
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
            <span className="font-medium text-muted">Why verify: </span>
            {item.description}
          </p>
          {item.label && <p className="mt-1 text-[12.5px] font-medium italic text-warn">{item.label}</p>}
          {item.evidence.length > 0 ? (
            <div className="mt-2 space-y-1.5">
              {item.evidence.map((e, i) => (
                <EvidenceLine key={i} ev={e} onViewSlide={onViewSlide} />
              ))}
            </div>
          ) : (
            <p className="mt-2 text-[12px] text-faint">Source: not present in the submission</p>
          )}
          {onRespond && <FindingControls findingKey={`verify:${item.id}`} value={response} onRespond={onRespond} />}
          {readOnly && response && <ResponseBadge r={response} />}
        </div>
      </div>
    </li>
  );
}

function ResponseBadge({ r }: { r: FindingResponse }) {
  return (
    <div className="mt-2 text-[12px] text-muted">
      Judge response: <span className="font-medium capitalize text-ink-2">{r.response}</span>
      {r.note && <> — {r.note}</>}
    </div>
  );
}

function FindingControls({ findingKey, value, onRespond, compact }: { findingKey: string; value?: FindingResponse; onRespond: RespondFn; compact?: boolean }) {
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState(value?.note ?? "");
  const [saving, setSaving] = useState(false);

  async function send(response: FindingResponse["response"], n = note) {
    setSaving(true);
    try {
      await onRespond(findingKey, response, n);
    } finally {
      setSaving(false);
    }
  }

  const opts: { key: FindingResponse["response"]; label: string; icon: ReactNode }[] = [
    { key: "agree", label: "Agree", icon: <ThumbsUp className="h-3 w-3" /> },
    { key: "disagree", label: "Disagree", icon: <ThumbsDown className="h-3 w-3" /> },
    { key: "unsure", label: "Unsure", icon: <CircleHelp className="h-3 w-3" /> },
  ];
  return (
    <div className={clsx("mt-2.5", compact && "pl-6")}>
      <div className="flex flex-wrap items-center gap-1.5">
        {opts.map((o) => (
          <button
            key={o.key}
            disabled={saving}
            onClick={() => {
              void send(o.key);
              if (o.key !== "agree") setNoteOpen(true);
            }}
            className={clsx(
              "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11.5px] font-medium transition-colors",
              value?.response === o.key
                ? o.key === "disagree"
                  ? "border-danger bg-danger-soft text-danger"
                  : o.key === "agree"
                    ? "border-ok bg-ok-soft text-ok"
                    : "border-line-strong bg-sunken text-ink"
                : "border-line text-muted hover:border-line-strong hover:text-ink",
            )}
          >
            {o.icon}
            {o.label}
          </button>
        ))}
        {value && !noteOpen && (
          <button onClick={() => setNoteOpen(true)} className="text-[11.5px] text-muted hover:text-ink hover:underline">
            {value.note ? "Edit note" : "Add note"}
          </button>
        )}
        {saving && <Loader2 className="h-3 w-3 animate-spin text-muted" />}
      </div>
      {noteOpen && value && (
        <div className="mt-2 flex gap-2">
          <input
            className="input h-8 py-1 text-[12.5px]"
            placeholder="Why? (optional, recorded in the audit trail)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                void send(value.response).then(() => setNoteOpen(false));
              }
            }}
          />
          <button
            onClick={() => void send(value.response).then(() => setNoteOpen(false))}
            className="rounded-md bg-sunken px-2.5 text-[12px] font-medium text-ink hover:bg-line"
          >
            Save
          </button>
        </div>
      )}
      {value?.note && !noteOpen && <p className="mt-1 text-[12px] text-muted">Your note: {value.note}</p>}
    </div>
  );
}

function IntegritySection({ integrity, onViewSlide }: { integrity: IntegrityReport | null; onViewSlide: ViewSlide }) {
  if (!integrity) {
    return (
      <Section id="integrity" icon={<ShieldAlert className="h-4 w-4" />} title="Submission integrity">
        <p className="text-[13px] text-muted">The integrity check could not run because the document was not processed. Manual review required.</p>
      </Section>
    );
  }
  const tone = integrityTone(integrity.status);
  const flags = integrity.flags.filter((f) => f.status !== "no_discrepancy_detected");
  const info = integrity.flags.filter((f) => f.status === "no_discrepancy_detected");
  return (
    <Section
      id="integrity"
      icon={tone === "ok" ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
      title="Submission integrity"
      subtitle="Checks for hidden or inconsistent content only"
    >
      <div className={clsx("flex items-start gap-2 text-[13.5px] font-semibold", tone === "ok" ? "text-ok" : tone === "danger" ? "text-danger" : "text-warn")}>
        <span>{tone === "ok" ? "✓" : "⚠"}</span>
        <span>{INTEGRITY_LABEL[integrity.status]}</span>
      </div>
      <p className="mt-1 text-[13px] text-ink-2">{integrity.summary}</p>
      {flags.length > 0 && (
        <ul className="mt-3 space-y-2">
          {flags.map((f, i) => (
            <li key={i} className="rounded-lg border border-line bg-canvas px-3 py-2 text-[12.5px]">
              <div className="text-ink-2">{f.detail}</div>
              <div className="mt-1.5 flex items-center gap-2">
                {f.slide_id && (
                  <button onClick={() => onViewSlide(f.slide_id!)} className="font-medium text-accent hover:underline">
                    View {slideLabel(f.slide_id)}
                  </button>
                )}
                {f.withheld_from_ai && <Badge tone="neutral">Withheld from AI analysis</Badge>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {info.length > 0 && (
        <p className="mt-3 text-[12px] text-muted">
          {info.length} visible passage{info.length > 1 ? "s" : ""} address evaluators directly. Visible text is not treated as hidden content.
        </p>
      )}
      <p className="mt-3 border-t border-line pt-2.5 text-[11.5px] leading-relaxed text-faint">{integrity.limitations}</p>
    </Section>
  );
}
