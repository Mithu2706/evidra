import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Check } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { DocumentViewer, type ViewerFocus } from "../../components/review/DocumentViewer";
import { EvaluationPanel, type FinalizeBody, type SubmitBody } from "../../components/review/EvaluationPanel";
import { JudgeBriefPanel } from "../../components/review/JudgeBriefPanel";
import { ErrorBlock, IntegrityBadge, LoadingBlock } from "../../components/ui";
import { api } from "../../lib/api";
import type { FindingResponse, ReviewPayload } from "../../lib/types";

const STEPS = [
  { title: "Review evidence", hint: "Read the original submission and inspect the evidence highlighted by Evidra." },
  { title: "Score independently", hint: "Score using your own judgment. AI scoring remains hidden." },
  { title: "Compare with AI", hint: "Review Evidra's preliminary assessment after submitting your independent score." },
  { title: "Final decision", hint: "Keep or revise your evaluation. Your final score is recorded in the audit trail." },
];

/** Active step (1–4), or 5 once the final evaluation is recorded. */
function stepIndex(p: ReviewPayload, hasDraftScores: boolean): number {
  if (p.revision) return 5;
  if (p.reveal) return 4;
  if (p.evaluation) return 3;
  return hasDraftScores ? 2 : 1;
}

export default function ReviewScreen() {
  const { assignmentId } = useParams();
  const id = Number(assignmentId);
  const qc = useQueryClient();
  const key = ["review", id];
  const { data, error, isLoading } = useQuery({
    queryKey: key,
    queryFn: () => api<ReviewPayload>(`/api/judge/assignments/${id}`),
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d || d.submission.status === "processing_failed") return false;
      return d.analysis.status === "pending" || d.analysis.status === "running" || d.submission.status === "processing" ? 3000 : false;
    },
  });

  const [current, setCurrent] = useState(0);
  const [hasDraftScores, setHasDraftScores] = useState(false);
  const [focus, setFocus] = useState<ViewerFocus | null>(null);

  const viewSlide = useCallback(
    (slideId: string, excerpt?: string) => {
      const idx = data?.document.slides.findIndex((s) => s.slide_key === slideId) ?? -1;
      if (idx >= 0) {
        setCurrent(idx);
        setFocus({ slideId, excerpt, nonce: Date.now() });
      }
    },
    [data],
  );

  useEffect(() => {
    if (focus && data && data.document.slides[current]?.slide_key !== focus.slideId) setFocus(null);
  }, [current]); // eslint-disable-line react-hooks/exhaustive-deps

  const setPayload = (p: ReviewPayload) => {
    qc.setQueryData(key, p);
    void qc.invalidateQueries({ queryKey: ["judge-dashboard"] });
  };

  const respond = useMutation({
    mutationFn: ({ k, response, note }: { k: string; response: FindingResponse["response"]; note: string }) =>
      api<{ finding_key: string; response: FindingResponse["response"]; note: string }>(
        `/api/judge/assignments/${id}/findings/${encodeURIComponent(k)}`,
        { method: "PUT", json: { response, note } },
      ),
    onSuccess: (r) =>
      qc.setQueryData<ReviewPayload>(key, (old) =>
        old ? { ...old, finding_responses: { ...old.finding_responses, [r.finding_key]: { response: r.response, note: r.note } } } : old,
      ),
  });

  if (isLoading) return <LoadingBlock label="Opening submission…" />;
  if (error || !data) return <div className="p-6"><ErrorBlock error={error} /></div>;

  const step = stepIndex(data, hasDraftScores);
  const activeHint = step <= 4 ? STEPS[step - 1] : null;

  const onSubmit = async (body: SubmitBody) => {
    setPayload(await api<ReviewPayload>(`/api/judge/assignments/${id}/submit`, { method: "POST", json: body }));
    // Show the AI assessment immediately after submission.
    setPayload(await api<ReviewPayload>(`/api/judge/assignments/${id}/reveal`, { method: "POST" }));
  };
  const onReveal = async () => setPayload(await api<ReviewPayload>(`/api/judge/assignments/${id}/reveal`, { method: "POST" }));
  const onFinalize = async (body: FinalizeBody) =>
    setPayload(await api<ReviewPayload>(`/api/judge/assignments/${id}/finalize`, { method: "POST", json: body }));

  return (
    <div className="flex h-[calc(100vh-56px)] flex-col">
      {/* context bar */}
      <div className="flex shrink-0 items-center gap-4 border-b border-line bg-surface px-4 py-2.5">
        <Link to="/judge" className="rounded-md p-1.5 text-muted hover:bg-sunken hover:text-ink" title="Back to my reviews">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0">
          <h1 className="truncate text-[15px] font-semibold text-ink">{data.submission.title}</h1>
          <div className="flex min-w-0 items-center gap-2 text-[12px] text-muted">
            <span className="truncate">
              {data.submission.team_name} · {data.round.name}
            </span>
            <span className="shrink-0">
              <IntegrityBadge status={data.submission.integrity_status} submissionStatus={data.submission.status} notAssessedCount={data.not_assessed.length} />
            </span>
          </div>
        </div>
        <ol className="ml-auto hidden shrink-0 items-center gap-1 lg:flex">
          {STEPS.map((s, i) => {
            const n = i + 1;
            const done = n < step;
            const active = n === step;
            return (
              <li key={s.title} className="flex items-center gap-1" title={s.hint}>
                <span
                  className={clsx(
                    "flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] font-medium",
                    active ? "bg-navy text-white" : done ? "text-ok" : "text-faint",
                  )}
                >
                  <span
                    className={clsx(
                      "flex h-4 w-4 items-center justify-center rounded-full text-[10px]",
                      active ? "bg-white/20" : done ? "bg-ok-soft" : "bg-sunken",
                    )}
                  >
                    {done ? <Check className="h-2.5 w-2.5" /> : n}
                  </span>
                  {s.title}
                </span>
                {n < STEPS.length && <span className="h-px w-3 bg-line-strong" />}
              </li>
            );
          })}
        </ol>
      </div>
      <div className="flex shrink-0 items-center gap-2 border-b border-line bg-canvas px-4 py-1.5 text-[12.5px] text-ink-2">
        {activeHint ? (
          <>
            <span className="font-semibold text-ink">
              Step {step} · {activeHint.title}
            </span>
            <span className="text-muted">— {activeHint.hint}</span>
          </>
        ) : (
          <>
            <Check className="h-3.5 w-3.5 text-ok" />
            <span className="font-semibold text-ink">Final evaluation recorded</span>
            <span className="text-muted">— your initial score, the AI preliminary assessment and your final score are in the audit trail.</span>
          </>
        )}
      </div>

      {/* three panes */}
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(340px,400px)]">
        <div className="min-h-0 border-r border-line">
          <DocumentViewer document={data.document} current={current} onChange={setCurrent} focus={focus} onClearFocus={() => setFocus(null)} />
        </div>
        <div className="scroll-thin min-h-0 overflow-y-auto bg-canvas">
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-canvas/95 px-4 py-2.5 backdrop-blur">
            <div>
              <div className="text-[14px] font-semibold text-ink">Judge brief</div>
              <div className="text-[11.5px] text-muted">AI-prepared evidence summary · every finding links to its source</div>
            </div>
          </div>
          <div className="p-4">
            <JudgeBriefPanel
              analysis={data.analysis}
              integrity={data.integrity}
              notAssessed={data.not_assessed}
              documentMessage={data.document.processing.message}
              onViewSlide={viewSlide}
              responses={data.finding_responses}
              readOnly={data.assignment.status === "completed"}
              onRespond={async (k, response, note) => {
                await respond.mutateAsync({ k, response, note });
              }}
            />
          </div>
        </div>
        <aside className="flex min-h-0 flex-col border-l border-line bg-surface">
          <div className="shrink-0 border-b border-line px-4 py-2.5">
            <div className="text-[14px] font-semibold text-ink">Your evaluation</div>
            <div className="text-[11.5px] text-muted">
              {data.revision
                ? "Final evaluation recorded"
                : data.evaluation
                  ? "Independent score submitted · compare, then keep or revise"
                  : `${data.round.criteria.length} criteria · scale 1–${data.round.score_scale_max} · score independently before AI reveal`}
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <EvaluationPanel payload={data} onSubmit={onSubmit} onReveal={onReveal} onFinalize={onFinalize} onViewSlide={viewSlide} onDraftChange={setHasDraftScores} />
          </div>
        </aside>
      </div>
    </div>
  );
}
