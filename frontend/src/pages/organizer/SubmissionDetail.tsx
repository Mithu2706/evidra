import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ChevronRight, RefreshCw } from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AuditTimeline } from "../../components/AuditTimeline";
import { DocumentViewer, type ViewerFocus } from "../../components/review/DocumentViewer";
import { JudgeBriefPanel } from "../../components/review/JudgeBriefPanel";
import { Badge, Button, Callout, Card, ErrorBlock, IntegrityBadge, LoadingBlock } from "../../components/ui";
import { api } from "../../lib/api";
import { ASSIGNMENT_LABEL, PROCESSING_STAGE_LABEL, formatDateTime, formatScore } from "../../lib/format";
import type { AuditEvent, SubmissionDetail } from "../../lib/types";

type Tab = "brief" | "processing" | "judges" | "audit";

export default function SubmissionDetailPage() {
  const { submissionId } = useParams();
  const id = Number(submissionId);
  const qc = useQueryClient();
  const { data, error, isLoading } = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api<SubmissionDetail>(`/api/submissions/${id}`),
    refetchInterval: (q) => (q.state.data?.submission.processing_stage || q.state.data?.submission.status === "processing" ? 2500 : false),
  });
  const audit = useQuery({
    queryKey: ["submission-audit", id, data?.submission.round_id],
    enabled: Boolean(data),
    queryFn: () => api<{ events: AuditEvent[] }>(`/api/rounds/${data!.submission.round_id}/audit?submission_id=${id}&limit=200`),
  });
  const reprocess = useMutation({
    mutationFn: () => api(`/api/submissions/${id}/reprocess`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["submission", id] }),
  });
  const [tab, setTab] = useState<Tab>("brief");
  const [current, setCurrent] = useState(0);
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

  if (isLoading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock error={error} />;
  const s = data.submission;
  const started = data.assignments.some((a) => a.status === "submitted" || a.status === "completed");

  return (
    <>
      <div className="mb-1 flex items-center gap-1 text-[12.5px] text-muted">
        <Link to="/org" className="hover:text-ink">
          Rounds
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link to={`/org/rounds/${s.round_id}/submissions`} className="hover:text-ink">
          Submissions
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-ink-2">{s.team_name}</span>
      </div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-tight">{s.title}</h1>
          <div className="text-[13px] text-muted">
            {s.team_name} · {s.file?.name} · uploaded {formatDateTime(s.created_at)}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {s.processing_stage && <Badge tone="accent">{PROCESSING_STAGE_LABEL[s.processing_stage] ?? s.processing_stage}…</Badge>}
          <IntegrityBadge status={s.integrity_status} submissionStatus={s.status} notAssessedCount={s.not_assessed_count} />
          <Button size="sm" icon={<RefreshCw className="h-3.5 w-3.5" />} disabled={started || Boolean(s.processing_stage)} loading={reprocess.isPending} onClick={() => reprocess.mutate()} title={started ? "Judges have already evaluated this submission" : "Re-run ingestion and analysis"}>
            Reprocess
          </Button>
        </div>
      </div>

      <div className="grid h-[calc(100vh-220px)] min-h-[560px] grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] overflow-hidden rounded-xl border border-line bg-surface shadow-card">
        <div className="min-h-0 border-r border-line">
          <DocumentViewer document={data.document} current={current} onChange={setCurrent} focus={focus} onClearFocus={() => setFocus(null)} />
        </div>
        <div className="flex min-h-0 flex-col">
          <div className="flex shrink-0 gap-1 border-b border-line px-3">
            {(
              [
                ["brief", "Judge brief"],
                ["processing", "Processing"],
                ["judges", `Judges (${data.assignments.length})`],
                ["audit", "Audit"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                onClick={() => setTab(k)}
                className={clsx("-mb-px border-b-2 px-3 py-2.5 text-[13px] font-medium", tab === k ? "border-navy text-ink" : "border-transparent text-muted hover:text-ink")}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto bg-canvas p-4">
            {tab === "brief" && (
              <JudgeBriefPanel
                analysis={data.analysis}
                integrity={data.integrity}
                notAssessed={data.not_assessed}
                documentMessage={data.document.processing.message}
                onViewSlide={viewSlide}
                readOnly
              />
            )}
            {tab === "processing" && <ProcessingTab data={data} />}
            {tab === "judges" && <JudgesTab data={data} />}
            {tab === "audit" && (
              <Card>
                <AuditTimeline events={audit.data?.events ?? []} />
              </Card>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function ProcessingTab({ data }: { data: SubmissionDetail }) {
  const p = data.document.processing;
  return (
    <div className="space-y-4">
      {p.message && <Callout tone="danger" title={p.message}>{p.error}</Callout>}
      <Card className="p-4">
        <div className="eyebrow mb-2">Ingestion pipeline</div>
        <dl className="grid grid-cols-[140px_1fr] gap-y-1.5 text-[13px]">
          {["validator", "parser", "renderer", "ocr", "integrity"].map((k) => (
            <div key={k} className="contents">
              <dt className="capitalize text-muted">{k === "ocr" ? "OCR" : k}</dt>
              <dd className="font-mono text-[12px] text-ink-2">{p.components[k] ?? "—"}</dd>
            </div>
          ))}
          <dt className="text-muted">Pages</dt>
          <dd className="tabular">{data.document.slides.length}</dd>
        </dl>
      </Card>
      <Card className="p-4">
        <div className="eyebrow mb-2">AI analysis</div>
        <div className="text-[13px]">
          Status: <span className="font-medium capitalize">{data.analysis.status}</span>
          {data.analysis.engine && <> · engine <span className="font-mono text-[12px]">{data.analysis.engine}</span></>}
          {data.analysis.model && <> · model <span className="font-mono text-[12px]">{data.analysis.model}</span></>}
        </div>
        {data.analysis.status === "failed" && <Callout tone="warn" className="mt-2" title={data.analysis.message}>{data.analysis.error}</Callout>}
        <p className="mt-2 text-[12px] text-muted">{data.analysis_history.length} analysis run(s) recorded. The AI's preliminary score is withheld until every assigned judge has finished.</p>
      </Card>
      {data.ai_assessment && (
        <Card className="p-4">
          <div className="eyebrow mb-1">AI preliminary assessment (post-judging)</div>
          <div className="text-[12px] font-medium text-accent-strong">{data.ai_assessment.label}</div>
          <div className="tabular mt-2 text-[22px] font-semibold">{formatScore(data.ai_assessment.overall_score)} <span className="text-[13px] font-normal text-faint">/ 100 · {formatScore(data.ai_assessment.assessed_weight)}% of rubric assessed</span></div>
          <ul className="mt-2 space-y-1 text-[12.5px]">
            {data.ai_assessment.criteria.map((c) => (
              <li key={c.criterion_id} className="flex justify-between gap-3">
                <span className="text-ink-2">{c.criterion}</span>
                <span className="tabular text-muted">{c.assessed ? formatScore(c.score) : "Not assessed"}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function JudgesTab({ data }: { data: SubmissionDetail }) {
  if (!data.assignments.length) return <Callout tone="neutral">No judges assigned yet. Assign judges from the round's Judges &amp; assignments tab.</Callout>;
  return (
    <div className="space-y-2">
      {data.assignments.map((a) => (
        <Card key={a.id} className="flex items-center gap-3 p-3.5">
          <div className="min-w-0 flex-1">
            <div className="text-[13.5px] font-medium">{a.judge.name}</div>
            <div className="text-[12px] text-muted">
              {a.opened_at ? `Opened ${formatDateTime(a.opened_at)}` : "Not opened yet"}
              {a.submitted_at && ` · submitted ${formatDateTime(a.submitted_at)}`}
            </div>
          </div>
          {a.final_score !== null && (
            <div className="text-right">
              <div className="tabular text-[16px] font-semibold">{formatScore(a.final_score)}</div>
              <div className="text-[11px] text-muted">{a.decision === "revised" ? "revised" : "kept"}</div>
            </div>
          )}
          <Badge tone={a.status === "completed" ? "ok" : a.status === "assigned" ? "neutral" : "accent"}>{ASSIGNMENT_LABEL[a.status]}</Badge>
        </Card>
      ))}
      {!data.judging_complete && <p className="px-1 text-[12px] text-faint">Individual scores are shown once all assigned judges have finished.</p>}
    </div>
  );
}
