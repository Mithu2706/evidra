import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DEFAULT_RUBRIC, RubricEditor, rubricTotal, type CriterionDraft } from "../../components/RubricEditor";
import { Button, Callout, Card, CardHeader, PageHeader } from "../../components/ui";
import { api } from "../../lib/api";
import type { Round } from "../../lib/types";

export default function RoundCreate() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [criteria, setCriteria] = useState<CriterionDraft[]>(DEFAULT_RUBRIC);
  const [limits, setLimits] = useState({ max_submissions: 500, max_file_size_mb: 25, max_pages: 30, judges_per_submission: 2, score_scale_max: 10 });
  const [types, setTypes] = useState<string[]>(["pdf", "pptx"]);

  const create = useMutation({
    mutationFn: () =>
      api<Round>("/api/rounds", {
        method: "POST",
        json: {
          name,
          description,
          ...limits,
          allowed_file_types: types,
          criteria: criteria.map(({ name, description, weight }) => ({ name, description, weight })),
        },
      }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["rounds"] });
      navigate(`/org/rounds/${r.id}/submissions`);
    },
  });

  const valid = name.trim().length >= 2 && rubricTotal(criteria) === 100 && criteria.every((c) => c.name.trim()) && types.length > 0;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="New evaluation round" title="Create a round" description="Define what judges evaluate and how submissions are accepted. The rubric can be edited until the first evaluation is submitted." />

      <div className="space-y-5">
        <Card>
          <CardHeader title="Round details" />
          <div className="space-y-4 p-5">
            <div>
              <label className="label">Name</label>
              <input className="input" placeholder="e.g. Climate Tech Challenge 2026 — Round 1" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="label">Description</label>
              <textarea className="input min-h-[80px]" placeholder="Context for judges: stage of the competition, what's expected from teams…" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Evaluation rubric" subtitle="Judges score each criterion; the weighted total is computed on a 0–100 scale." />
          <div className="p-5">
            <RubricEditor value={criteria} onChange={setCriteria} />
            <div className="mt-4 flex items-center gap-3">
              <label className="text-[13px] text-ink-2">Score each criterion from 1 to</label>
              <select className="input w-24" value={limits.score_scale_max} onChange={(e) => setLimits({ ...limits, score_scale_max: Number(e.target.value) })}>
                {[5, 7, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Submission limits & review" />
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <NumberField label="Maximum submissions" value={limits.max_submissions} onChange={(v) => setLimits({ ...limits, max_submissions: v })} />
            <NumberField label="Judges per submission" value={limits.judges_per_submission} onChange={(v) => setLimits({ ...limits, judges_per_submission: v })} />
            <NumberField label="Max file size (MB)" value={limits.max_file_size_mb} onChange={(v) => setLimits({ ...limits, max_file_size_mb: v })} />
            <NumberField label="Max pages / slides" value={limits.max_pages} onChange={(v) => setLimits({ ...limits, max_pages: v })} />
            <div className="sm:col-span-2">
              <label className="label">Accepted formats</label>
              <div className="flex gap-4">
                {["pdf", "pptx"].map((t) => (
                  <label key={t} className="inline-flex items-center gap-2 text-[13.5px]">
                    <input type="checkbox" checked={types.includes(t)} onChange={(e) => setTypes(e.target.checked ? [...types, t] : types.filter((x) => x !== t))} />
                    {t.toUpperCase()}
                  </label>
                ))}
                <span className="text-[12.5px] text-faint">GitHub repositories and demo videos are planned for later versions.</span>
              </div>
            </div>
          </div>
        </Card>

        {create.error && <Callout tone="danger">{(create.error as Error).message}</Callout>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => navigate(-1)}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!valid} loading={create.isPending} onClick={() => create.mutate()}>
            Create round
          </Button>
        </div>
      </div>
    </div>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input type="number" min={1} className="input tabular" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}
