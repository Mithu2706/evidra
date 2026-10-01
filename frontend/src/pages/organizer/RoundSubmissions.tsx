import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { FileUp, Loader2, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Callout, Card, CardHeader, EmptyState, ErrorBlock, IntegrityBadge, LoadingBlock } from "../../components/ui";
import { api } from "../../lib/api";
import { PROCESSING_STAGE_LABEL, formatBytes, formatRelative } from "../../lib/format";
import type { SubmissionSummary } from "../../lib/types";
import { useRound } from "./RoundLayout";

interface QueuedFile {
  key: string;
  file: File;
  team: string;
  title: string;
  status: "ready" | "uploading" | "done" | "error";
  error?: string;
}

const STAGE_BADGE: Record<string, { label: string; tone: "neutral" | "accent" | "ok" | "warn" | "danger" }> = {
  processing: { label: "Processing", tone: "accent" },
  failed: { label: "Processing failed", tone: "danger" },
  awaiting_review: { label: "Awaiting review", tone: "neutral" },
  in_review: { label: "In review", tone: "accent" },
  completed: { label: "Completed", tone: "ok" },
};

function guessTeam(name: string): string {
  return name
    .replace(/\.(pdf|pptx)$/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function RoundSubmissions() {
  const { round } = useRound();
  const qc = useQueryClient();
  const { data, error, isLoading } = useQuery({
    queryKey: ["submissions", round.id],
    queryFn: () => api<SubmissionSummary[]>(`/api/rounds/${round.id}/submissions`),
    refetchInterval: (q) => (q.state.data?.some((s) => s.status === "processing" || s.status === "uploaded" || s.processing_stage) ? 2500 : false),
  });
  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function addFiles(files: FileList | File[]) {
    const accepted = Array.from(files).filter((f) => /\.(pdf|pptx)$/i.test(f.name));
    setQueue((q) => [
      ...q,
      ...accepted.map((f) => ({ key: `${f.name}-${f.size}-${Math.random()}`, file: f, team: guessTeam(f.name), title: "", status: "ready" as const })),
    ]);
  }

  async function uploadAll() {
    for (const item of queue.filter((q) => q.status === "ready" || q.status === "error")) {
      setQueue((q) => q.map((x) => (x.key === item.key ? { ...x, status: "uploading", error: undefined } : x)));
      const form = new FormData();
      form.append("file", item.file);
      form.append("team_name", item.team || guessTeam(item.file.name));
      form.append("title", item.title);
      try {
        await api(`/api/rounds/${round.id}/submissions`, { method: "POST", body: form });
        setQueue((q) => q.map((x) => (x.key === item.key ? { ...x, status: "done" } : x)));
      } catch (e) {
        setQueue((q) => q.map((x) => (x.key === item.key ? { ...x, status: "error", error: (e as Error).message } : x)));
      }
    }
    void qc.invalidateQueries({ queryKey: ["submissions", round.id] });
    void qc.invalidateQueries({ queryKey: ["dashboard", round.id] });
    setTimeout(() => setQueue((q) => q.filter((x) => x.status !== "done")), 1200);
  }

  if (isLoading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock error={error} />;
  const pending = queue.filter((q) => q.status !== "done").length;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Upload submissions"
          subtitle={`PDF or PowerPoint (.pptx) · up to ${round.max_file_size_mb} MB · max ${round.max_pages} pages · ${data.length}${round.max_submissions ? ` / ${round.max_submissions}` : ""} submissions`}
        />
        <div className="p-5">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              addFiles(e.dataTransfer.files);
            }}
            onClick={() => input.current?.click()}
            className={clsx(
              "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
              dragging ? "border-accent bg-accent-soft" : "border-line-strong bg-canvas hover:border-faint",
            )}
          >
            <FileUp className="h-6 w-6 text-muted" />
            <div className="mt-2 text-[14px] font-medium">Drop pitch decks here or click to browse</div>
            <div className="mt-1 text-[12.5px] text-muted">Each file is validated, parsed, rendered, checked for integrity issues and turned into a judge brief.</div>
            <input ref={input} type="file" multiple accept=".pdf,.pptx" className="hidden" onChange={(e) => e.target.files && addFiles(e.target.files)} />
          </div>

          {queue.length > 0 && (
            <div className="mt-4 overflow-hidden rounded-lg border border-line">
              {queue.map((q) => (
                <div key={q.key} className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-3 border-b border-line px-3 py-2 last:border-0">
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium">{q.file.name}</div>
                    <div className="text-[11.5px] text-muted">{formatBytes(q.file.size)}</div>
                    {q.error && <div className="text-[11.5px] text-danger">{q.error}</div>}
                  </div>
                  <input className="input h-8 py-1 text-[13px]" placeholder="Team name" value={q.team} disabled={q.status === "uploading"} onChange={(e) => setQueue((all) => all.map((x) => (x.key === q.key ? { ...x, team: e.target.value } : x)))} />
                  <input className="input h-8 py-1 text-[13px]" placeholder="Project title (optional)" value={q.title} disabled={q.status === "uploading"} onChange={(e) => setQueue((all) => all.map((x) => (x.key === q.key ? { ...x, title: e.target.value } : x)))} />
                  <div className="flex w-16 justify-end">
                    {q.status === "uploading" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted" />
                    ) : q.status === "done" ? (
                      <Badge tone="ok">Uploaded</Badge>
                    ) : (
                      <button onClick={() => setQueue((all) => all.filter((x) => x.key !== q.key))} className="rounded p-1 text-faint hover:bg-sunken hover:text-ink" aria-label="Remove">
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {pending > 0 && (
            <div className="mt-3 flex justify-end">
              <Button variant="primary" icon={<Upload className="h-4 w-4" />} onClick={uploadAll} disabled={queue.some((q) => q.status === "uploading")}>
                Upload {pending} file{pending > 1 ? "s" : ""}
              </Button>
            </div>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Submissions" subtitle="Listed in upload order. Evidra does not rank or reject submissions." />
        {data.length === 0 ? (
          <EmptyState title="No submissions yet" description="Uploaded decks appear here while they're processed." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="border-b border-line bg-canvas text-left text-[11.5px] uppercase tracking-wide text-faint">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Submission</th>
                  <th className="px-3 py-2.5 font-medium">File</th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                  <th className="px-3 py-2.5 font-medium">Integrity</th>
                  <th className="px-3 py-2.5 font-medium">Brief</th>
                  <th className="px-3 py-2.5 font-medium">Judges</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {data.map((s) => {
                  const stage = STAGE_BADGE[s.stage ?? "processing"];
                  return (
                    <tr key={s.id} className="border-b border-line last:border-0 hover:bg-canvas">
                      <td className="px-5 py-3">
                        <div className="font-medium text-ink">{s.title}</div>
                        <div className="text-[12px] text-muted">
                          {s.team_name} · {formatRelative(s.created_at)}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-muted">
                        <span className="uppercase">{s.file?.type}</span> · {s.file?.pages ?? "—"} pp · {s.file ? formatBytes(s.file.size_bytes) : ""}
                      </td>
                      <td className="px-3 py-3">
                        {s.processing_stage ? (
                          <Badge tone="accent" icon={<Loader2 className="h-3 w-3 animate-spin" />}>
                            {PROCESSING_STAGE_LABEL[s.processing_stage] ?? s.processing_stage}
                          </Badge>
                        ) : (
                          <Badge tone={stage.tone}>{stage.label}</Badge>
                        )}
                        {s.not_assessed_count > 0 && s.status !== "processing_failed" && (
                          <div className="mt-1 text-[11.5px] text-muted">{s.not_assessed_count} item{s.not_assessed_count === 1 ? "" : "s"} not assessed</div>
                        )}
                      </td>
                      <td className="px-3 py-3"><IntegrityBadge status={s.integrity_status} submissionStatus={s.status} notAssessedCount={s.not_assessed_count} /></td>
                      <td className="px-3 py-3">
                        {s.analysis_status === "completed" ? (
                          <Badge tone="ok">Ready</Badge>
                        ) : s.analysis_status === "failed" ? (
                          <Badge tone="warn">AI unavailable</Badge>
                        ) : s.status === "processing_failed" ? (
                          <span className="text-faint">—</span>
                        ) : (
                          <Badge>Pending</Badge>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        {s.assignments.length === 0 ? (
                          <span className="text-[12px] text-faint">Unassigned</span>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {s.assignments.map((a) => (
                              <Badge key={a.id} tone={a.status === "completed" ? "ok" : a.status === "assigned" ? "neutral" : "accent"}>
                                {a.judge_name.split(" ")[0]}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Link to={`/org/submissions/${s.id}`} className="text-[12.5px] font-medium text-accent hover:underline">
                          Details
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {data.some((s) => s.status === "processing_failed") && (
        <Callout tone="warn" title="Some documents could not be fully processed">
          These submissions still need human review. Judges can open the original file; no AI findings are generated for them.
        </Callout>
      )}
    </div>
  );
}
