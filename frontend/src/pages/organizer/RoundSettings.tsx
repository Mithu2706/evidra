import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useState } from "react";
import { RubricEditor, newCriterion, rubricTotal, type CriterionDraft } from "../../components/RubricEditor";
import { Button, Callout, Card, CardHeader } from "../../components/ui";
import { api } from "../../lib/api";
import type { Round } from "../../lib/types";
import { useRound } from "./RoundLayout";

export default function RoundSettings() {
  const { round } = useRound();
  const qc = useQueryClient();
  const [criteria, setCriteria] = useState<CriterionDraft[]>(() => round.criteria.map((c) => newCriterion(c.name, c.weight, c.description)));
  const [meta, setMeta] = useState({
    name: round.name,
    description: round.description,
    status: round.status,
    max_submissions: round.max_submissions ?? 500,
    max_file_size_mb: round.max_file_size_mb,
    max_pages: round.max_pages,
    judges_per_submission: round.judges_per_submission,
  });
  const [saved, setSaved] = useState<string | null>(null);

  const onSaved = (r: Round, what: string) => {
    qc.setQueryData(["round", round.id], r);
    void qc.invalidateQueries({ queryKey: ["rounds"] });
    setSaved(what);
    setTimeout(() => setSaved(null), 2500);
  };

  const saveMeta = useMutation({
    mutationFn: () => api<Round>(`/api/rounds/${round.id}`, { method: "PATCH", json: meta }),
    onSuccess: (r) => onSaved(r, "Round settings saved."),
  });
  const saveRubric = useMutation({
    mutationFn: () =>
      api<Round>(`/api/rounds/${round.id}/criteria`, {
        method: "PUT",
        json: { criteria: criteria.map(({ name, description, weight }) => ({ name, description, weight })) },
      }),
    onSuccess: (r) => onSaved(r, "Rubric saved. Judge briefs are being regenerated."),
  });

  const locked = Boolean(round.rubric_locked);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <Card>
        <CardHeader
          title="Evaluation rubric"
          subtitle={`Scale 1–${round.score_scale_max} per criterion · weighted to 0–100`}
          action={locked && <span className="inline-flex items-center gap-1 text-[12.5px] text-muted"><Lock className="h-3.5 w-3.5" /> Locked</span>}
        />
        <div className="space-y-4 p-5">
          {locked && (
            <Callout tone="neutral" title="Rubric locked">
              Judges have already submitted evaluations against this rubric. Changing it now would make scores incomparable.
            </Callout>
          )}
          <RubricEditor value={criteria} onChange={setCriteria} disabled={locked} />
          {saveRubric.error && <Callout tone="danger">{(saveRubric.error as Error).message}</Callout>}
          {!locked && (
            <div className="flex justify-end">
              <Button variant="primary" disabled={rubricTotal(criteria) !== 100} loading={saveRubric.isPending} onClick={() => saveRubric.mutate()}>
                Save rubric
              </Button>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Round settings" />
        <div className="space-y-4 p-5">
          <div>
            <label className="label">Name</label>
            <input className="input" value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="input min-h-[80px]" value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Num label="Max submissions" value={meta.max_submissions} onChange={(v) => setMeta({ ...meta, max_submissions: v })} />
            <Num label="Judges / submission" value={meta.judges_per_submission} onChange={(v) => setMeta({ ...meta, judges_per_submission: v })} />
            <Num label="Max file size (MB)" value={meta.max_file_size_mb} onChange={(v) => setMeta({ ...meta, max_file_size_mb: v })} />
            <Num label="Max pages" value={meta.max_pages} onChange={(v) => setMeta({ ...meta, max_pages: v })} />
          </div>
          <div>
            <label className="label">Status</label>
            <select className="input" value={meta.status} onChange={(e) => setMeta({ ...meta, status: e.target.value as Round["status"] })}>
              <option value="draft">Draft</option>
              <option value="open">Open — accepting submissions</option>
              <option value="closed">Closed — no new submissions</option>
            </select>
          </div>
          {saveMeta.error && <Callout tone="danger">{(saveMeta.error as Error).message}</Callout>}
          <div className="flex justify-end">
            <Button variant="primary" loading={saveMeta.isPending} onClick={() => saveMeta.mutate()}>
              Save settings
            </Button>
          </div>
        </div>
      </Card>
      {saved && (
        <div className="animate-slide-up fixed bottom-6 right-6 z-40">
          <Callout tone="ok">{saved}</Callout>
        </div>
      )}
    </div>
  );
}

function Num({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input type="number" min={1} className="input tabular" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}
