export type Role = "organizer" | "judge";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  title: string | null;
  organization: string | null;
}

export interface Criterion {
  id: number;
  name: string;
  description: string;
  weight: number;
  position: number;
}

export interface Round {
  id: number;
  name: string;
  description: string;
  status: "draft" | "open" | "closed";
  score_scale_max: number;
  max_submissions: number | null;
  max_file_size_mb: number;
  max_pages: number;
  allowed_file_types: string[];
  judges_per_submission: number;
  created_at: string;
  criteria: Criterion[];
  submission_count: number;
  rubric_locked?: boolean;
}

export type IntegrityStatus =
  | "no_discrepancy_detected"
  | "potential_discrepancy"
  | "suspicious_instruction_detected"
  | "manual_review_required";

export interface IntegrityFlag {
  slide_id: string | null;
  type: string;
  status: IntegrityStatus;
  location: "slide_text" | "speaker_notes" | "slide";
  excerpt: string;
  detail: string;
  withheld_from_ai: boolean;
}

export interface IntegrityReport {
  status: IntegrityStatus;
  summary: string;
  flags: IntegrityFlag[];
  method?: string;
  limitations: string;
}

export interface NotAssessedItem {
  area: string;
  reason: string;
  slide_id: string | null;
}

export interface EvidenceRef {
  slide_id: string;
  excerpt: string;
  page_number: number | null;
  verified: boolean;
  via: "text" | "speaker_notes" | "ocr" | "unknown";
}

export type Severity = "low" | "medium" | "high";

export interface VerifyItem {
  id: string;
  title: string;
  description: string;
  type:
    | "unsupported_claim"
    | "feasibility_gap"
    | "missing_information"
    | "potential_similarity"
    | "inconsistency"
    | "integrity";
  severity: Severity;
  evidence: EvidenceRef[];
  label: string | null;
  related_criteria: string[];
}

export interface JudgeBrief {
  overview: string;
  target_users: string | null;
  evidence_highlights: { id: string; label: string; evidence: EvidenceRef[] }[];
  strengths: { id: string; text: string; evidence: EvidenceRef[] }[];
  verify_these: VerifyItem[];
  not_assessed: NotAssessedItem[];
  integrity: { status: IntegrityStatus; message: string; flags: IntegrityFlag[]; limitations: string };
  rubric_coverage: {
    criterion_id: number;
    criterion: string;
    evidence: EvidenceRef[];
    coverage: "addressed" | "limited" | "not_found";
  }[];
  provenance: { engine: string; model: string | null; pipeline_version: string; stages: string[]; note: string };
}

export interface AnalysisInfo {
  id?: number;
  status: "pending" | "running" | "completed" | "failed";
  engine?: string;
  model?: string | null;
  message?: string;
  error?: string;
  completed_at?: string | null;
  brief?: JudgeBrief;
}

export interface CriterionAssessment {
  criterion_id: number;
  criterion: string;
  assessed: boolean;
  finding: string;
  evidence: EvidenceRef[];
  issues: { type: string; description: string; severity: Severity }[];
  score: number | null;
  not_assessed_reason: string | null;
}

export interface AIAssessment {
  label: string;
  score_scale_max: number;
  overall_score: number | null;
  assessed_weight: number;
  criteria: CriterionAssessment[];
  engine: string;
  model: string | null;
}

export interface SlideInfo {
  id: number;
  slide_key: string;
  page_number: number;
  title: string | null;
  text: string;
  speaker_notes: string | null;
  ocr_text: string | null;
  ocr_status: string;
  has_image: boolean;
  image_url: string | null;
  thumb_url: string | null;
  has_visual_content: boolean;
  links: string[];
  integrity_flags: IntegrityFlag[];
  processing_notes: string[];
}

export interface DocumentInfo {
  slides: SlideInfo[];
  file: { name: string; type: string; pages: number | null; download_url: string } | null;
  processing: {
    status: string;
    stage: string | null;
    message: string | null;
    error: string | null;
    components: Record<string, string>;
  };
}

export interface CriterionScore {
  criterion_id: number;
  score: number;
  comment?: string;
}

export interface Evaluation {
  criterion_scores: CriterionScore[];
  weighted_score: number;
  overall_comment: string;
  recommendation: "advance" | "discuss" | "do_not_advance" | null;
  submitted_at: string;
}

export interface RevealInfo {
  revealed_at: string;
  ai_available: boolean;
  message?: string;
  assessment?: AIAssessment;
  ai_score?: number | null;
}

export interface RevisionInfo {
  decision: "kept" | "revised";
  human_initial_score: number;
  ai_score: number | null;
  human_revised_score: number;
  revision_reason: string;
  initial_criterion_scores: CriterionScore[];
  revised_criterion_scores: CriterionScore[];
  initial_to_ai_difference: number | null;
  initial_to_revised_difference: number;
  revision_direction: "no_change" | "toward_ai" | "away_from_ai" | "ai_unavailable";
  created_at: string;
}

export type AssignmentStatus = "assigned" | "in_progress" | "submitted" | "completed";

export interface FindingResponse {
  response: "agree" | "disagree" | "unsure";
  note: string;
  updated_at?: string;
}

export interface ReviewPayload {
  assignment: {
    id: number;
    status: AssignmentStatus;
    opened_at: string | null;
    submitted_at: string | null;
    completed_at: string | null;
  };
  submission: { id: number; team_name: string; title: string; status: string; integrity_status: IntegrityStatus | null };
  round: { id: number; name: string; score_scale_max: number; criteria: Criterion[] };
  document: DocumentInfo;
  integrity: IntegrityReport | null;
  not_assessed: NotAssessedItem[];
  analysis: AnalysisInfo;
  evaluation: Evaluation | null;
  finding_responses: Record<string, FindingResponse>;
  reveal: RevealInfo | null;
  revision: RevisionInfo | null;
}

export interface AssignmentRow {
  id: number;
  status: AssignmentStatus;
  assigned_at: string;
  opened_at: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  review_minutes: number | null;
  round_name?: string;
  submission: {
    id: number;
    team_name: string;
    title: string;
    status: string;
    integrity_status: IntegrityStatus | null;
    file_type: string | null;
    pages: number | null;
    analysis_status: string;
    verify_count: number;
    high_priority_count: number;
    not_assessed_count: number;
  };
  final_score: number | null;
}

export interface SubmissionSummary {
  id: number;
  round_id: number;
  team_name: string;
  title: string;
  status: "uploaded" | "processing" | "ready" | "partially_processed" | "processing_failed";
  processing_stage: string | null;
  processing_error: string | null;
  integrity_status: IntegrityStatus | null;
  integrity_summary: string | null;
  not_assessed_count: number;
  analysis_status: string;
  file: { name: string; type: string; size_bytes: number; pages: number | null } | null;
  created_at: string;
  processed_at: string | null;
  assignments: { id: number; judge_id: number; judge_name: string; status: AssignmentStatus }[];
  stage?: "processing" | "failed" | "awaiting_review" | "in_review" | "completed";
}

export interface AuditEvent {
  id: number;
  action: string;
  actor: string;
  actor_id: number | null;
  round_id: number | null;
  submission_id: number | null;
  entity_type: string | null;
  entity_id: number | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Dashboard {
  round: Round;
  totals: {
    submissions: number;
    processed: number;
    processing: number;
    failed: number;
    awaiting_review: number;
    in_review: number;
    completed: number;
    remaining: number;
  };
  assignments: { total: number; completed: number; in_progress: number; not_started: number; completion_pct: number };
  avg_review_minutes: number | null;
  integrity_warnings: number;
  ai_failures: number;
  attention: { submission_id: number; team_name: string; kind: string; reason: string }[];
  judges: { id: number; name: string; assigned: number; completed: number; in_progress: number; avg_review_minutes: number | null }[];
  recent_activity: { id: number; action: string; actor: string; submission_id: number | null; created_at: string }[];
}

export interface Judge extends User {
  assigned: number;
  completed: number;
  temporary_password?: string;
}

export interface ResultsRow {
  submission_id: number;
  team_name: string;
  title: string;
  judging_complete: boolean;
  judges_completed: number;
  judges_assigned: number;
  human_final_mean: number | null;
  human_initial_mean: number | null;
  human_final_min: number | null;
  human_final_max: number | null;
  spread: number | null;
  needs_calibration: boolean;
  recommendations: Record<string, number>;
  revisions: number;
  ai_score: number | null;
  integrity_status: IntegrityStatus | null;
}

export interface Results {
  rows: ResultsRow[];
  anchoring: {
    evaluations_finalized: number;
    kept: number;
    revised: number;
    toward_ai: number;
    away_from_ai: number;
    ai_unavailable: number;
    mean_abs_initial_to_ai: number | null;
    mean_abs_revised_to_ai: number | null;
    mean_abs_revision: number | null;
    note: string;
  };
}

export interface SubmissionDetail {
  submission: SubmissionSummary;
  document: DocumentInfo;
  analysis: AnalysisInfo;
  integrity: IntegrityReport | null;
  not_assessed: NotAssessedItem[];
  judging_complete: boolean;
  ai_assessment: AIAssessment | null;
  assignments: {
    id: number;
    judge: User;
    status: AssignmentStatus;
    opened_at: string | null;
    submitted_at: string | null;
    completed_at: string | null;
    final_score: number | null;
    decision: string | null;
  }[];
  analysis_history: AnalysisInfo[];
}

export interface Health {
  status: string;
  ai_engine: string;
  ai_model: string | null;
  ai_configured: boolean;
  ocr_engine: string | null;
  slide_rendering: { pdf: boolean; pptx: boolean };
  future_sources: Record<string, string>;
}
