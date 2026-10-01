import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { AuditTimeline } from "../../components/AuditTimeline";
import { Card, ErrorBlock, LoadingBlock } from "../../components/ui";
import { api } from "../../lib/api";
import type { AuditEvent, SubmissionSummary } from "../../lib/types";
import { useRound } from "./RoundLayout";

const FILTERS = [
  { v: "", label: "All events" },
  { v: "submission", label: "Submissions & processing" },
  { v: "analysis", label: "AI analysis" },
  { v: "integrity", label: "Integrity" },
  { v: "assignment", label: "Assignments" },
  { v: "review", label: "Reviews opened" },
  { v: "finding", label: "Responses to AI findings" },
  { v: "evaluation", label: "Evaluations & revisions" },
  { v: "ai.revealed", label: "AI reveals" },
  { v: "rubric", label: "Rubric changes" },
];

export default function RoundAudit() {
  const { round } = useRound();
  const [action, setAction] = useState("");
  const [submission, setSubmission] = useState("");
  const [limit, setLimit] = useState(100);
  const subs = useQuery({ queryKey: ["submissions", round.id], queryFn: () => api<SubmissionSummary[]>(`/api/rounds/${round.id}/submissions`) });
  const params = new URLSearchParams({ limit: String(limit) });
  if (action) params.set("action", action);
  if (submission) params.set("submission_id", submission);
  const { data, error, isLoading } = useQuery({
    queryKey: ["audit", round.id, action, submission, limit],
    queryFn: () => api<{ total: number; events: AuditEvent[] }>(`/api/rounds/${round.id}/audit?${params}`),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <select className="input w-auto" value={action} onChange={(e) => setAction(e.target.value)}>
          {FILTERS.map((f) => (
            <option key={f.v} value={f.v}>
              {f.label}
            </option>
          ))}
        </select>
        <select className="input w-auto" value={submission} onChange={(e) => setSubmission(e.target.value)}>
          <option value="">All submissions</option>
          {subs.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.team_name} — {s.title}
            </option>
          ))}
        </select>
        {data && <span className="ml-auto text-[12.5px] text-muted">{data.total} events · append-only</span>}
      </div>
      {isLoading ? (
        <LoadingBlock />
      ) : error || !data ? (
        <ErrorBlock error={error} />
      ) : (
        <Card>
          <AuditTimeline events={data.events} submissions={subs.data ?? []} />
          {data.total > data.events.length && (
            <button onClick={() => setLimit((l) => l + 100)} className="flex w-full items-center justify-center gap-1 border-t border-line py-2.5 text-[13px] font-medium text-accent hover:bg-canvas">
              Load more <ChevronDown className="h-4 w-4" />
            </button>
          )}
        </Card>
      )}
    </div>
  );
}
