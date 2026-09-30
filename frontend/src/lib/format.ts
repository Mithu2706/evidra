import type { AssignmentStatus, IntegrityStatus, Severity, VerifyItem } from "./types";

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
  return formatDateTime(iso);
}

export function formatMinutes(min: number | null | undefined): string {
  if (min === null || min === undefined) return "—";
  if (min < 1) return "<1 min";
  if (min < 60) return `${Math.round(min)} min`;
  return `${Math.floor(min / 60)} h ${Math.round(min % 60)} min`;
}

export function formatScore(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(digits).replace(/\.0$/, "");
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function slideLabel(slideId: string, page?: number | null): string {
  const n = page ?? parseInt(slideId.replace(/\D/g, ""), 10);
  return `Slide ${n}`;
}

export const INTEGRITY_LABEL: Record<IntegrityStatus, string> = {
  no_discrepancy_detected: "No discrepancy detected",
  potential_discrepancy: "Potential discrepancy",
  suspicious_instruction_detected: "Hidden instruction-like text",
  manual_review_required: "Manual review required",
};

export const ASSIGNMENT_LABEL: Record<AssignmentStatus, string> = {
  assigned: "Not started",
  in_progress: "In review",
  submitted: "Submitted · AI not yet reviewed",
  completed: "Completed",
};

export const SEVERITY_LABEL: Record<Severity, string> = { high: "High priority", medium: "Medium", low: "Low" };

export const VERIFY_TYPE_LABEL: Record<VerifyItem["type"], string> = {
  unsupported_claim: "Unsupported claim",
  feasibility_gap: "Feasibility",
  missing_information: "Missing information",
  potential_similarity: "Differentiation",
  inconsistency: "Inconsistency",
  integrity: "Integrity",
};

export const RECOMMENDATION_LABEL: Record<string, string> = {
  advance: "Advance",
  discuss: "Discuss",
  do_not_advance: "Do not advance",
};

export const DIRECTION_LABEL: Record<string, string> = {
  no_change: "No change",
  toward_ai: "Moved toward AI",
  away_from_ai: "Moved away from AI",
  ai_unavailable: "AI unavailable",
};

export const PROCESSING_STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  validating: "Validating file",
  parsing: "Extracting text",
  rendering: "Rendering slides",
  ocr: "Reading rendered slides",
  integrity: "Integrity check",
  ai_analysis: "Preparing brief",
};

export function actionLabel(action: string): string {
  const map: Record<string, string> = {
    "auth.login": "Signed in",
    "round.created": "Created round",
    "round.updated": "Updated round settings",
    "rubric.updated": "Updated rubric",
    "submission.uploaded": "Uploaded submission",
    "submission.ingestion_started": "Started document processing",
    "submission.ingested": "Processed document (evidence pack created)",
    "submission.ingestion_failed": "Document processing failed",
    "submission.reprocess_requested": "Requested reprocessing",
    "integrity.flagged": "Integrity check raised a warning",
    "analysis.completed": "Generated judge brief",
    "analysis.failed": "AI analysis failed",
    "assignment.created": "Assigned judge",
    "assignment.removed": "Removed judge assignment",
    "judge.invited": "Added judge",
    "review.opened": "Opened review",
    "finding.responded": "Responded to AI finding",
    "evaluation.submitted": "Submitted independent evaluation",
    "ai.revealed": "Revealed AI assessment",
    "evaluation.kept": "Kept original score",
    "evaluation.revised": "Revised score after AI reveal",
    "results.exported": "Exported anchoring data",
  };
  return map[action] ?? action;
}
