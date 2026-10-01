import clsx from "clsx";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { Button } from "./ui";

export interface CriterionDraft {
  key: string;
  name: string;
  description: string;
  weight: number;
}

let counter = 0;
export const newCriterion = (name = "", weight = 0, description = ""): CriterionDraft => ({
  key: `c${++counter}`,
  name,
  description,
  weight,
});

export const DEFAULT_RUBRIC = (): CriterionDraft[] => [
  newCriterion("Problem Understanding", 20, "How clearly the team defines the problem, who experiences it and why it matters."),
  newCriterion("Innovation", 25, "Novelty of the approach and how it differs from existing solutions."),
  newCriterion("Technical Feasibility", 20, "Whether the solution can realistically be built and operated, with evidence."),
  newCriterion("Impact", 20, "Expected benefit for the target users or society, and how credibly it is supported."),
  newCriterion("Scalability", 15, "Ability to grow beyond a pilot: deployment path, costs, integration and business model."),
];

export function rubricTotal(c: CriterionDraft[]): number {
  return Math.round(c.reduce((s, x) => s + (Number(x.weight) || 0), 0) * 100) / 100;
}

export function RubricEditor({ value, onChange, disabled }: { value: CriterionDraft[]; onChange: (v: CriterionDraft[]) => void; disabled?: boolean }) {
  const total = rubricTotal(value);
  const update = (key: string, patch: Partial<CriterionDraft>) => onChange(value.map((c) => (c.key === key ? { ...c, ...patch } : c)));

  return (
    <div>
      <div className="overflow-hidden rounded-xl border border-line">
        <div className="grid grid-cols-[24px_minmax(0,1fr)_110px_36px] gap-3 border-b border-line bg-canvas px-3 py-2 text-[11.5px] font-medium uppercase tracking-wide text-faint">
          <span />
          <span>Criterion &amp; guidance for judges</span>
          <span className="text-right">Weight</span>
          <span />
        </div>
        {value.map((c) => (
          <div key={c.key} className="grid grid-cols-[24px_minmax(0,1fr)_110px_36px] items-start gap-3 border-b border-line bg-surface px-3 py-3 last:border-0">
            <GripVertical className="mt-2 h-4 w-4 text-line-strong" />
            <div className="space-y-1.5">
              <input className="input font-medium" placeholder="Criterion name" value={c.name} disabled={disabled} onChange={(e) => update(c.key, { name: e.target.value })} />
              <input
                className="input text-[13px] text-ink-2"
                placeholder="What should judges look for? (shown next to the score)"
                value={c.description}
                disabled={disabled}
                onChange={(e) => update(c.key, { description: e.target.value })}
              />
            </div>
            <div className="relative">
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                className="input tabular pr-7 text-right"
                value={Number.isNaN(c.weight) ? "" : c.weight}
                disabled={disabled}
                onChange={(e) => update(c.key, { weight: parseFloat(e.target.value) })}
              />
              <span className="pointer-events-none absolute right-3 top-2 text-[13px] text-faint">%</span>
            </div>
            <button
              className="mt-1.5 rounded-md p-1.5 text-faint hover:bg-danger-soft hover:text-danger disabled:opacity-30"
              disabled={disabled || value.length <= 1}
              onClick={() => onChange(value.filter((x) => x.key !== c.key))}
              aria-label="Remove criterion"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Button size="sm" variant="ghost" icon={<Plus className="h-4 w-4" />} disabled={disabled} onClick={() => onChange([...value, newCriterion()])}>
          Add criterion
        </Button>
        <div className="flex items-center gap-3 text-[13px]">
          <div className="h-1.5 w-40 overflow-hidden rounded-full bg-sunken">
            <div className={clsx("h-full rounded-full transition-all", total === 100 ? "bg-ok" : total > 100 ? "bg-danger" : "bg-[#d98b1c]")} style={{ width: `${Math.min(total, 100)}%` }} />
          </div>
          <span className={clsx("tabular font-medium", total === 100 ? "text-ok" : "text-warn")}>
            {total}% {total === 100 ? "✓" : "— weights must total 100%"}
          </span>
        </div>
      </div>
    </div>
  );
}
