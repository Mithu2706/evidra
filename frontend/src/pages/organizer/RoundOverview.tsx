import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, Bot, CircleSlash, Clock, FileWarning, Gauge, ShieldAlert, UserX } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, CardHeader, EmptyState, ErrorBlock, LoadingBlock, ProgressBar, Stat } from "../../components/ui";
import { api } from "../../lib/api";
import { actionLabel, formatMinutes, formatRelative } from "../../lib/format";
import type { Dashboard } from "../../lib/types";
import { useRound } from "./RoundLayout";

const ATTENTION_ICON: Record<string, ReactNode> = {
  processing_failed: <FileWarning className="h-4 w-4 text-danger" />,
  partial: <CircleSlash className="h-4 w-4 text-warn" />,
  integrity: <ShieldAlert className="h-4 w-4 text-warn" />,
  ai_failed: <Bot className="h-4 w-4 text-warn" />,
  unassigned: <UserX className="h-4 w-4 text-muted" />,
};

export default function RoundOverview() {
  const { round } = useRound();
  const { data, error, isLoading } = useQuery({
    queryKey: ["dashboard", round.id],
    queryFn: () => api<Dashboard>(`/api/rounds/${round.id}/dashboard`),
    refetchInterval: (q) => (q.state.data?.totals.processing ? 3000 : 15000),
  });
  if (isLoading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock error={error} />;
  const t = data.totals;

  return (
    <div className="space-y-6">
      {/* funnel */}
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-[15px] font-semibold">Judging pipeline</h3>
            <p className="text-[13px] text-muted">Every submission is reviewed by humans. Evidra prepares the evidence.</p>
          </div>
          {t.processing > 0 && <Badge tone="accent">{t.processing} processing…</Badge>}
        </div>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-4">
          <FunnelStep label="Submissions" value={t.submissions} sub={`${t.failed} could not be processed`} />
          <FunnelStep label="Processed" value={t.processed} sub="Evidence pack + brief ready" />
          <FunnelStep label="Completed" value={t.completed} sub="All assigned judges finished" tone="ok" />
          <FunnelStep label="Remaining" value={t.remaining} sub={`${t.awaiting_review} awaiting · ${t.in_review} in review`} />
        </div>
        <StageBar totals={t} />
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Completion" value={`${Math.round(data.assignments.completion_pct)}%`} icon={<Gauge className="h-4 w-4" />} hint={`${data.assignments.completed} of ${data.assignments.total} reviews`} />
        <Stat label="Avg. judge review time" value={formatMinutes(data.avg_review_minutes)} icon={<Clock className="h-4 w-4" />} hint="Open → submit" />
        <Stat label="Needs manual attention" value={data.attention.length} tone={data.attention.length ? "warn" : undefined} icon={<AlertTriangle className="h-4 w-4" />} />
        <Stat label="Integrity warnings" value={data.integrity_warnings} tone={data.integrity_warnings ? "warn" : undefined} icon={<ShieldAlert className="h-4 w-4" />} />
        <Stat label="AI processing failures" value={data.ai_failures} tone={data.ai_failures ? "danger" : undefined} icon={<Bot className="h-4 w-4" />} hint="Human review continues" />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Requires attention" subtitle="Processing problems, integrity warnings and unassigned submissions" />
          {data.attention.length === 0 ? (
            <EmptyState title="Nothing needs attention" description="All submissions processed without warnings." />
          ) : (
            <ul className="divide-y divide-line">
              {data.attention.map((a, i) => (
                <li key={i}>
                  <Link to={`/org/submissions/${a.submission_id}`} className="flex items-start gap-3 px-5 py-3 hover:bg-canvas">
                    <span className="mt-0.5">{ATTENTION_ICON[a.kind]}</span>
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-medium text-ink">{a.team_name}</div>
                      <div className="text-[12.5px] text-muted">{a.reason}</div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Judge progress" action={<Link to="assignments" className="text-[12.5px] font-medium text-accent hover:underline">Manage</Link>} />
            {data.judges.length === 0 ? (
              <EmptyState title="No judges assigned yet" />
            ) : (
              <ul className="divide-y divide-line">
                {data.judges.map((j) => (
                  <li key={j.id} className="px-5 py-3">
                    <div className="flex items-center justify-between text-[13px]">
                      <span className="font-medium">{j.name}</span>
                      <span className="tabular text-muted">
                        {j.completed}/{j.assigned} · {formatMinutes(j.avg_review_minutes)} avg
                      </span>
                    </div>
                    <ProgressBar className="mt-2" value={(100 * j.completed) / Math.max(j.assigned, 1)} tone="ok" />
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader title="Recent activity" action={<Link to="audit" className="text-[12.5px] font-medium text-accent hover:underline">Full audit history</Link>} />
            <ul className="divide-y divide-line">
              {data.recent_activity.map((e) => (
                <li key={e.id} className="flex items-start justify-between gap-3 px-5 py-2.5 text-[12.5px]">
                  <div className="min-w-0">
                    <span className="font-medium text-ink">{e.actor.replace(/ \((organizer|judge)\)$/, "")}</span>{" "}
                    <span className="text-muted">{lowerFirst(actionLabel(e.action))}</span>
                  </div>
                  <span className="shrink-0 text-faint">{formatRelative(e.created_at)}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <p className="text-center text-[12px] text-faint">Evidra does not rank submissions, reject submissions or select winners. All decisions are made by judges.</p>
    </div>
  );
}

function lowerFirst(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1);
}

function FunnelStep({ label, value, sub, tone }: { label: string; value: number; sub: string; tone?: "ok" }) {
  return (
    <div className="bg-surface px-4 py-3.5">
      <div className="text-[12.5px] font-medium text-muted">{label}</div>
      <div className={clsx("tabular mt-1 text-[30px] font-semibold leading-none tracking-tight", tone === "ok" ? "text-ok" : "text-ink")}>{value}</div>
      <div className="mt-1.5 text-[12px] text-faint">{sub}</div>
    </div>
  );
}

function StageBar({ totals: t }: { totals: Dashboard["totals"] }) {
  const parts = [
    { k: "Completed", v: t.completed, c: "bg-ok" },
    { k: "In review", v: t.in_review, c: "bg-accent" },
    { k: "Awaiting review", v: t.awaiting_review, c: "bg-[#b9c7ee]" },
    { k: "Processing", v: t.processing, c: "bg-line-strong" },
    { k: "Failed", v: t.failed, c: "bg-danger" },
  ];
  const total = Math.max(t.submissions, 1);
  return (
    <div className="mt-4">
      <div className="flex h-2 overflow-hidden rounded-full bg-sunken">
        {parts.map((p) => p.v > 0 && <div key={p.k} className={clsx(p.c, "transition-all")} style={{ width: `${(100 * p.v) / total}%` }} />)}
      </div>
      <div className="mt-2 flex flex-wrap gap-4 text-[12px] text-muted">
        {parts.map((p) => (
          <span key={p.k} className="inline-flex items-center gap-1.5">
            <span className={clsx("h-2 w-2 rounded-sm", p.c)} />
            {p.k} <span className="tabular font-medium text-ink-2">{p.v}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
