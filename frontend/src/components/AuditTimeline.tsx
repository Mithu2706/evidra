import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { INTEGRITY_LABEL, actionLabel, formatDateTime } from "../lib/format";
import type { AuditEvent, IntegrityStatus, SubmissionSummary } from "../lib/types";
import { EmptyState } from "./ui";

function tone(action: string): string {
  if (action.includes("failed")) return "bg-danger";
  if (action.startsWith("integrity")) return "bg-[#d98b1c]";
  if (action.startsWith("evaluation") || action === "ai.revealed") return "bg-navy";
  if (action.startsWith("analysis") || action.startsWith("submission")) return "bg-accent";
  return "bg-line-strong";
}

function summary(e: AuditEvent): string | null {
  const d = e.details as Record<string, unknown>;
  switch (e.action) {
    case "evaluation.submitted":
      return `Weighted score ${d.weighted_score}${d.recommendation ? ` · ${String(d.recommendation).replace(/_/g, " ")}` : ""}${d.review_minutes !== undefined ? ` · ${d.review_minutes} min` : ""}`;
    case "ai.revealed":
      return d.ai_available ? `AI preliminary ${d.ai_score_shown} shown after human score ${d.human_initial_score}` : "AI assessment unavailable";
    case "evaluation.revised":
    case "evaluation.kept":
      return `${d.human_initial_score} → ${d.human_revised_score} (AI ${d.ai_score ?? "n/a"})${d.reason ? ` · “${d.reason}”` : ""}`;
    case "finding.responded":
      return `${String(d.response)} · ${d.finding}${d.note ? ` · “${d.note}”` : ""}`;
    case "submission.ingested":
      return `${d.pages} pages · ${INTEGRITY_LABEL[d.integrity_status as IntegrityStatus] ?? String(d.integrity_status)} · ${d.not_assessed_items} not assessed`;
    case "integrity.flagged":
      return String(d.summary ?? "");
    case "analysis.failed":
    case "submission.ingestion_failed":
      return String(d.error ?? "");
    case "analysis.completed":
      return `${d.engine}${d.model ? ` (${d.model})` : ""} · ${d.verify_items} evidence checks`;
    case "assignment.created":
    case "assignment.removed":
      return String(d.judge ?? "");
    case "submission.uploaded":
      return String(d.filename ?? "");
    default:
      return null;
  }
}

export function AuditTimeline({ events, submissions = [] }: { events: AuditEvent[]; submissions?: SubmissionSummary[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const names = new Map(submissions.map((s) => [s.id, s.team_name]));
  if (!events.length) return <EmptyState title="No events" description="Actions on this round will appear here." />;
  return (
    <ul className="divide-y divide-line">
      {events.map((e) => {
        const s = summary(e);
        return (
          <li key={e.id}>
            <button onClick={() => setOpen(open === e.id ? null : e.id)} className="flex w-full items-start gap-3 px-5 py-3 text-left hover:bg-canvas">
              <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", tone(e.action))} />
              <div className="min-w-0 flex-1">
                <div className="text-[13px]">
                  <span className="font-medium text-ink">{e.actor}</span> <span className="text-ink-2">{actionLabel(e.action).charAt(0).toLowerCase() + actionLabel(e.action).slice(1)}</span>
                  {e.submission_id && names.get(e.submission_id) && <span className="text-muted"> · {names.get(e.submission_id)}</span>}
                </div>
                {s && <div className="mt-0.5 truncate text-[12.5px] text-muted">{s}</div>}
                {open === e.id && (
                  <pre className="scroll-thin mt-2 max-h-64 overflow-auto rounded-md bg-sunken p-2.5 font-mono text-[11.5px] text-ink-2">
                    {JSON.stringify({ action: e.action, entity: `${e.entity_type ?? ""}#${e.entity_id ?? ""}`, ...e.details }, null, 2)}
                  </pre>
                )}
              </div>
              <span className="tabular shrink-0 text-[12px] text-faint">{formatDateTime(e.created_at)}</span>
              <ChevronRight className={clsx("mt-0.5 h-3.5 w-3.5 shrink-0 text-faint transition-transform", open === e.id && "rotate-90")} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
