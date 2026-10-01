import { useQuery } from "@tanstack/react-query";
import { Download, FlaskConical, Scale } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Callout, Card, CardHeader, ErrorBlock, IntegrityBadge, LoadingBlock } from "../../components/ui";
import { api, authUrl } from "../../lib/api";
import { RECOMMENDATION_LABEL, formatScore } from "../../lib/format";
import type { Results } from "../../lib/types";
import { useRound } from "./RoundLayout";

export default function RoundResults() {
  const { round } = useRound();
  const { data, error, isLoading } = useQuery({ queryKey: ["results", round.id], queryFn: () => api<Results>(`/api/rounds/${round.id}/results`) });
  if (isLoading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock error={error} />;
  const a = data.anchoring;

  return (
    <div className="space-y-6">
      <Callout tone="neutral" icon={<Scale className="h-4 w-4" />} title="Aggregate human results — no ranking">
        Submissions are listed alphabetically. Scores appear once every assigned judge has finished. Evidra does not rank submissions or pick winners; use these figures to
        support the panel's discussion. The AI preliminary score is shown for reference only.
      </Callout>

      <Card className="overflow-hidden">
        <CardHeader title="Results by submission" subtitle="Weighted scores on a 0–100 scale (judges' final decisions)" />
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="border-b border-line bg-canvas text-left text-[11.5px] uppercase tracking-wide text-faint">
              <tr>
                <th className="px-5 py-2.5 font-medium">Submission</th>
                <th className="px-3 py-2.5 font-medium">Judging</th>
                <th className="px-3 py-2.5 text-right font-medium">Human mean</th>
                <th className="px-3 py-2.5 text-right font-medium">Range</th>
                <th className="px-3 py-2.5 font-medium">Recommendations</th>
                <th className="px-3 py-2.5 text-right font-medium">Revisions</th>
                <th className="px-3 py-2.5 text-right font-medium">AI prelim.</th>
                <th className="px-5 py-2.5 font-medium">Integrity</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.submission_id} className="border-b border-line last:border-0 hover:bg-canvas">
                  <td className="px-5 py-3">
                    <Link to={`/org/submissions/${r.submission_id}`} className="font-medium text-ink hover:underline">
                      {r.team_name}
                    </Link>
                    <div className="truncate text-[12px] text-muted">{r.title}</div>
                  </td>
                  <td className="px-3 py-3">
                    {r.judging_complete ? (
                      <Badge tone="ok">Complete</Badge>
                    ) : (
                      <span className="tabular text-[12.5px] text-muted">
                        {r.judges_completed}/{r.judges_assigned} judges done
                      </span>
                    )}
                  </td>
                  <td className="tabular px-3 py-3 text-right text-[14px] font-semibold">
                    {formatScore(r.human_final_mean)}
                    {r.human_initial_mean !== null && r.human_initial_mean !== r.human_final_mean && (
                      <div className="text-[11px] font-normal text-faint">initial {formatScore(r.human_initial_mean)}</div>
                    )}
                  </td>
                  <td className="tabular px-3 py-3 text-right text-muted">
                    {r.human_final_min !== null ? `${formatScore(r.human_final_min)}–${formatScore(r.human_final_max)}` : "—"}
                    {r.needs_calibration && (
                      <div>
                        <Badge tone="warn">Judges disagree</Badge>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(r.recommendations).map(([k, v]) => (
                        <Badge key={k}>
                          {RECOMMENDATION_LABEL[k] ?? k} ×{v}
                        </Badge>
                      ))}
                      {!Object.keys(r.recommendations).length && <span className="text-faint">—</span>}
                    </div>
                  </td>
                  <td className="tabular px-3 py-3 text-right text-muted">{r.judging_complete ? r.revisions : "—"}</td>
                  <td className="tabular px-3 py-3 text-right text-accent-strong">{formatScore(r.ai_score)}</td>
                  <td className="px-5 py-3">
                    <IntegrityBadge status={r.integrity_status} compact />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardHeader
          title={
            <span className="inline-flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-muted" /> AI anchoring study data
            </span>
          }
          subtitle="What judges did after the AI assessment was revealed"
          action={
            <a href={authUrl(`/api/rounds/${round.id}/results/anchoring.csv`)}>
              <Button size="sm" icon={<Download className="h-4 w-4" />}>
                Export CSV
              </Button>
            </a>
          }
        />
        <div className="grid grid-cols-2 gap-px bg-line md:grid-cols-4">
          <Metric label="Finalized evaluations" value={a.evaluations_finalized} />
          <Metric label="Kept initial score" value={a.kept} />
          <Metric label="Revised after reveal" value={a.revised} sub={`${a.toward_ai} toward AI · ${a.away_from_ai} away`} />
          <Metric label="Mean |initial − AI|" value={formatScore(a.mean_abs_initial_to_ai)} sub={`after revision: ${formatScore(a.mean_abs_revised_to_ai)}`} />
        </div>
        <p className="border-t border-line px-5 py-3 text-[12.5px] text-muted">{a.note}</p>
      </Card>
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-surface px-5 py-4">
      <div className="text-[12.5px] text-muted">{label}</div>
      <div className="tabular mt-1 text-[22px] font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-[12px] text-faint">{sub}</div>}
    </div>
  );
}
