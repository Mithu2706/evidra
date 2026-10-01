import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router-dom";
import { Badge, ErrorBlock, LoadingBlock } from "../../components/ui";
import { api } from "../../lib/api";
import type { Round } from "../../lib/types";

export function useRound() {
  return useOutletContext<{ round: Round }>();
}

const TABS = [
  { to: "", label: "Overview", end: true },
  { to: "submissions", label: "Submissions" },
  { to: "assignments", label: "Judges & assignments" },
  { to: "results", label: "Results" },
  { to: "audit", label: "Audit history" },
  { to: "settings", label: "Rubric & settings" },
];

export default function RoundLayout() {
  const { roundId } = useParams();
  const { data, error, isLoading } = useQuery({ queryKey: ["round", Number(roundId)], queryFn: () => api<Round>(`/api/rounds/${roundId}`) });
  if (isLoading) return <LoadingBlock />;
  if (error || !data) return <ErrorBlock error={error} />;

  return (
    <>
      <div className="mb-1 flex items-center gap-1 text-[12.5px] text-muted">
        <Link to="/org" className="hover:text-ink">
          Rounds
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="truncate text-ink-2">{data.name}</span>
      </div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <h1 className="text-[22px] font-semibold tracking-tight">{data.name}</h1>
        <Badge tone={data.status === "open" ? "ok" : "neutral"} className="capitalize">
          {data.status}
        </Badge>
      </div>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <NavLink
            key={t.label}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              clsx(
                "-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-[13.5px] font-medium transition-colors",
                isActive ? "border-navy text-ink" : "border-transparent text-muted hover:text-ink",
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={{ round: data }} />
    </>
  );
}
