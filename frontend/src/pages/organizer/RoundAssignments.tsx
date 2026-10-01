import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, Loader2, Shuffle, UserPlus } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Callout, Card, CardHeader, Dialog, ErrorBlock, LoadingBlock } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { ASSIGNMENT_LABEL } from "../../lib/format";
import type { Judge, SubmissionSummary } from "../../lib/types";
import { useRound } from "./RoundLayout";

export default function RoundAssignments() {
  const { round } = useRound();
  const qc = useQueryClient();
  const subs = useQuery({ queryKey: ["submissions", round.id], queryFn: () => api<SubmissionSummary[]>(`/api/rounds/${round.id}/submissions`) });
  const judges = useQuery({ queryKey: ["judges", round.id], queryFn: () => api<Judge[]>(`/api/rounds/${round.id}/judges`) });
  const [busyCell, setBusyCell] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [invite, setInvite] = useState(false);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["submissions", round.id] });
    void qc.invalidateQueries({ queryKey: ["judges", round.id] });
    void qc.invalidateQueries({ queryKey: ["dashboard", round.id] });
  };

  const auto = useMutation({
    mutationFn: () => api<{ created: number }>(`/api/rounds/${round.id}/assignments/auto`, { method: "POST", json: {} }),
    onSuccess: refresh,
    onError: (e) => setError((e as Error).message),
  });

  async function toggle(s: SubmissionSummary, j: Judge) {
    const existing = s.assignments.find((a) => a.judge_id === j.id);
    const cell = `${s.id}-${j.id}`;
    setBusyCell(cell);
    setError(null);
    try {
      if (existing) await api(`/api/assignments/${existing.id}`, { method: "DELETE" });
      else await api(`/api/rounds/${round.id}/assignments`, { method: "POST", json: { submission_id: s.id, judge_id: j.id } });
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusyCell(null);
    }
  }

  if (subs.isLoading || judges.isLoading) return <LoadingBlock />;
  if (subs.error || judges.error) return <ErrorBlock error={subs.error ?? judges.error} />;
  const S = subs.data!;
  const J = judges.data!;
  const under = S.filter((s) => s.assignments.length < round.judges_per_submission).length;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        {J.map((j) => (
          <Card key={j.id} className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sunken text-[12px] font-semibold text-ink-2">
                {j.name
                  .split(" ")
                  .map((p) => p[0])
                  .join("")
                  .slice(0, 2)}
              </div>
              <div className="min-w-0">
                <div className="truncate text-[13.5px] font-medium">{j.name}</div>
                <div className="truncate text-[12px] text-muted">{j.title ?? j.email}</div>
              </div>
              <div className="tabular ml-auto text-right text-[12px] text-muted">
                <div className="text-[15px] font-semibold text-ink">{j.assigned}</div>
                assigned
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <CardHeader
          title="Assignment matrix"
          subtitle={`Target: ${round.judges_per_submission} judges per submission. Click a cell to assign or unassign. Started reviews can't be unassigned.`}
          action={
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" icon={<UserPlus className="h-4 w-4" />} onClick={() => setInvite(true)}>
                Add judge
              </Button>
              <Button size="sm" variant="primary" icon={<Shuffle className="h-4 w-4" />} loading={auto.isPending} disabled={!under} onClick={() => auto.mutate()}>
                Auto-assign {under ? `(${under} short)` : ""}
              </Button>
            </div>
          }
        />
        {error && <Callout tone="danger" className="m-4">{error}</Callout>}
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="border-b border-line bg-canvas text-[11.5px] uppercase tracking-wide text-faint">
              <tr>
                <th className="px-5 py-2.5 text-left font-medium">Submission</th>
                {J.map((j) => (
                  <th key={j.id} className="px-3 py-2.5 text-center font-medium normal-case tracking-normal text-ink-2">
                    {j.name}
                  </th>
                ))}
                <th className="px-5 py-2.5 text-right font-medium">Coverage</th>
              </tr>
            </thead>
            <tbody>
              {S.map((s) => (
                <tr key={s.id} className="border-b border-line last:border-0">
                  <td className="px-5 py-2.5">
                    <div className="font-medium">{s.team_name}</div>
                    <div className="truncate text-[12px] text-muted">{s.title}</div>
                  </td>
                  {J.map((j) => {
                    const a = s.assignments.find((x) => x.judge_id === j.id);
                    const cell = `${s.id}-${j.id}`;
                    const locked = a && a.status !== "assigned";
                    return (
                      <td key={j.id} className="px-3 py-2.5 text-center">
                        <button
                          disabled={Boolean(locked) || busyCell === cell}
                          onClick={() => toggle(s, j)}
                          title={a ? ASSIGNMENT_LABEL[a.status] : "Assign"}
                          className={clsx(
                            "inline-flex h-7 min-w-[92px] items-center justify-center gap-1 rounded-md border px-2 text-[11.5px] font-medium transition-colors",
                            !a && "border-dashed border-line-strong text-faint hover:border-accent hover:text-accent",
                            a?.status === "assigned" && "border-navy bg-navy text-white hover:bg-[#23365e]",
                            a && a.status !== "assigned" && a.status !== "completed" && "cursor-default border-accent bg-accent-soft text-accent-strong",
                            a?.status === "completed" && "cursor-default border-[#c9ead8] bg-ok-soft text-ok",
                          )}
                        >
                          {busyCell === cell ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : a ? (
                            <>
                              {a.status === "completed" && <Check className="h-3 w-3" />}
                              {a.status === "assigned" ? "Assigned" : a.status === "completed" ? "Done" : "In review"}
                            </>
                          ) : (
                            "+ Assign"
                          )}
                        </button>
                      </td>
                    );
                  })}
                  <td className="px-5 py-2.5 text-right">
                    <Badge tone={s.assignments.length >= round.judges_per_submission ? "ok" : "warn"}>
                      {s.assignments.length}/{round.judges_per_submission}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <InviteJudge open={invite} onClose={() => setInvite(false)} roundId={round.id} onDone={refresh} />
    </div>
  );
}

function InviteJudge({ open, onClose, roundId, onDone }: { open: boolean; onClose: () => void; roundId: number; onDone: () => void }) {
  const [form, setForm] = useState({ name: "", email: "", title: "" });
  const [created, setCreated] = useState<Judge | null>(null);
  const m = useMutation({
    mutationFn: () => api<Judge>(`/api/rounds/${roundId}/judges`, { method: "POST", json: { ...form, title: form.title || null } }),
    onSuccess: (j) => {
      setCreated(j);
      onDone();
    },
  });
  const close = () => {
    setCreated(null);
    setForm({ name: "", email: "", title: "" });
    m.reset();
    onClose();
  };
  return (
    <Dialog
      open={open}
      onClose={close}
      title="Add a judge"
      footer={
        created ? (
          <Button variant="primary" onClick={close}>
            Done
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button variant="primary" loading={m.isPending} disabled={!form.name || !form.email} onClick={() => m.mutate()}>
              Add judge
            </Button>
          </>
        )
      }
    >
      {created ? (
        <Callout tone="ok" title={`${created.name} can now sign in`}>
          Share this temporary password securely: <code className="rounded bg-surface px-1 font-mono">{created.temporary_password}</code>. It is shown only once.
        </Callout>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="label">Full name</label>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label">Title / affiliation (optional)</label>
            <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          {m.error && <Callout tone="danger">{(m.error as Error).message}</Callout>}
        </div>
      )}
    </Dialog>
  );
}
