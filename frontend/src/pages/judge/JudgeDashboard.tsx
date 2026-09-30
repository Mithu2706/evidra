import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, FileText, Inbox, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, ErrorBlock, IntegrityBadge, LoadingBlock, PageHeader, ProgressBar, Stat } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ASSIGNMENT_LABEL, formatMinutes, formatRelative, formatScore } from "../../lib/format";
import type { AssignmentRow } from "../../lib/types";

interface JudgeDashboardData {
  stats: { assigned: number; completed: number; remaining: number; in_progress: number; avg_review_minutes: number | null; needs_attention: number };
  assignments: AssignmentRow[];
  attention_ids: number[];
}

export default function JudgeDashboard() {
  const { user } = useAuth();
  const { data, error, isLoading } = useQuery({
    queryKey: ["judge-dashboard"],
    queryFn: () => api<JudgeDashboardData>("/api/judge/dashboard"),
  });
  if (isLoading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock error={error} />;

  const { stats, assignments } = data;
  const attention = new Set(data.attention_ids);
  const next = assignments.find((a) => a.status === "in_progress" || a.status === "submitted") ?? assignments.find((a) => a.status === "assigned");
  const pct = stats.assigned ? (100 * stats.completed) / stats.assigned : 0;
  const open = assignments.filter((a) => a.status !== "completed");
  const done = assignments.filter((a) => a.status === "completed");

  return (
    <>
      <PageHeader
        eyebrow="Judge workspace"
        title={`Welcome back, ${user?.name.split(" ")[0]}`}
        description="Each submission comes with an evidence brief. Read the original, verify what matters, and score independently — the AI assessment stays hidden until you submit."
        actions={
          next && (
            <Link to={`/judge/review/${next.id}`}>
              <Button variant="primary" icon={<ArrowRight className="h-4 w-4" />}>
                {next.status === "assigned" ? "Start next review" : "Continue review"}
              </Button>
            </Link>
          )
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Assigned" value={stats.assigned} icon={<Inbox className="h-4 w-4" />} />
        <Stat label="Completed" value={stats.completed} icon={<CheckCircle2 className="h-4 w-4" />} hint={<ProgressBar value={pct} tone="ok" />} />
        <Stat label="Remaining" value={stats.remaining} icon={<ListChecks className="h-4 w-4" />} />
        <Stat label="Avg. review time" value={formatMinutes(stats.avg_review_minutes)} icon={<Clock className="h-4 w-4" />} hint="Open → submit" />
        <Stat label="Need attention" value={stats.needs_attention} tone={stats.needs_attention ? "warn" : undefined} icon={<AlertTriangle className="h-4 w-4" />} hint="Integrity or processing notes" />
      </div>

      <h2 className="mb-3 mt-8 text-[15px] font-semibold">To review</h2>
      {open.length === 0 ? (
        <Card>
          <EmptyState icon={<CheckCircle2 className="h-5 w-5" />} title="You're all caught up" description="No open reviews. New assignments will appear here." />
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {open.map((a) => (
            <AssignmentCard key={a.id} a={a} attention={attention.has(a.id)} />
          ))}
        </div>
      )}

      {done.length > 0 && (
        <>
          <h2 className="mb-3 mt-8 text-[15px] font-semibold">Completed</h2>
          <Card className="overflow-hidden">
            <table className="w-full text-[13px]">
              <thead className="border-b border-line bg-canvas text-left text-[11.5px] uppercase tracking-wide text-faint">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Submission</th>
                  <th className="px-4 py-2.5 font-medium">Finished</th>
                  <th className="px-4 py-2.5 font-medium">Review time</th>
                  <th className="px-4 py-2.5 text-right font-medium">Your final score</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {done.map((a) => (
                  <tr key={a.id} className="border-b border-line last:border-0 hover:bg-canvas">
                    <td className="px-4 py-3">
                      <div className="font-medium text-ink">{a.submission.title}</div>
                      <div className="text-[12px] text-muted">{a.submission.team_name}</div>
                    </td>
                    <td className="px-4 py-3 text-muted">{formatRelative(a.completed_at)}</td>
                    <td className="tabular px-4 py-3 text-muted">{formatMinutes(a.review_minutes)}</td>
                    <td className="tabular px-4 py-3 text-right font-semibold">{formatScore(a.final_score)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link to={`/judge/review/${a.id}`} className="text-[12.5px] font-medium text-accent hover:underline">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </>
  );
}

function AssignmentCard({ a, attention }: { a: AssignmentRow; attention: boolean }) {
  const s = a.submission;
  return (
    <Link to={`/judge/review/${a.id}`} className="group">
      <Card className={clsx("h-full p-4 transition-all group-hover:border-line-strong group-hover:shadow-pop", attention && "border-warn-line")}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-[14.5px] font-semibold text-ink">{s.title}</div>
            <div className="mt-0.5 text-[12.5px] text-muted">
              {s.team_name} · {a.round_name}
            </div>
          </div>
          <Badge tone={a.status === "assigned" ? "neutral" : "accent"}>{ASSIGNMENT_LABEL[a.status]}</Badge>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Badge icon={<FileText className="h-3 w-3" />}>
            {s.file_type?.toUpperCase()} · {s.pages ?? "?"} slides
          </Badge>
          <IntegrityBadge status={s.integrity_status} compact />
          {s.analysis_status === "failed" && <Badge tone="warn">AI analysis unavailable</Badge>}
          {s.status === "processing_failed" && <Badge tone="danger">Manual review required</Badge>}
        </div>
        <div className="mt-3 flex items-center gap-4 border-t border-line pt-3 text-[12.5px] text-muted">
          <span>
            <span className="tabular font-semibold text-ink">{s.verify_count}</span> to verify
            {s.high_priority_count > 0 && <span className="text-danger"> ({s.high_priority_count} high)</span>}
          </span>
          <span>
            <span className="tabular font-semibold text-ink">{s.not_assessed_count}</span> not assessed
          </span>
          <span className="ml-auto inline-flex items-center gap-1 font-medium text-accent opacity-0 transition-opacity group-hover:opacity-100">
            Open <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </Card>
    </Link>
  );
}
