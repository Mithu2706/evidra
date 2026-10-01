import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FolderOpen, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, ErrorBlock, LoadingBlock, PageHeader } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type { Round } from "../../lib/types";

export default function OrgHome() {
  const { data, error, isLoading } = useQuery({ queryKey: ["rounds"], queryFn: () => api<Round[]>("/api/rounds") });
  if (isLoading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock error={error} />;

  return (
    <>
      <PageHeader
        eyebrow="Organizer"
        title="Evaluation rounds"
        description="Each round has its own rubric, submissions and judging panel."
        actions={
          <Link to="/org/rounds/new">
            <Button variant="primary" icon={<Plus className="h-4 w-4" />}>
              New round
            </Button>
          </Link>
        }
      />
      {data.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FolderOpen className="h-5 w-5" />}
            title="No rounds yet"
            description="Create a round, define the rubric and upload submissions to get started."
            action={
              <Link to="/org/rounds/new">
                <Button variant="primary">Create your first round</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((r) => (
            <Link key={r.id} to={`/org/rounds/${r.id}`} className="group">
              <Card className="h-full p-5 transition-all group-hover:border-line-strong group-hover:shadow-pop">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-[16px] font-semibold text-ink">{r.name}</h2>
                  <Badge tone={r.status === "open" ? "ok" : "neutral"} className="capitalize">
                    {r.status}
                  </Badge>
                </div>
                <p className="mt-1.5 line-clamp-2 text-[13px] text-muted">{r.description}</p>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {r.criteria.map((c) => (
                    <Badge key={c.id}>
                      {c.name} · {c.weight}%
                    </Badge>
                  ))}
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-line pt-3 text-[12.5px] text-muted">
                  <span>
                    <span className="tabular font-semibold text-ink">{r.submission_count}</span> submissions · created {formatDateTime(r.created_at)}
                  </span>
                  <span className="inline-flex items-center gap-1 font-medium text-accent">
                    Open <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
