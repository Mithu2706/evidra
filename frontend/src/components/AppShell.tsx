import clsx from "clsx";
import { LogOut } from "lucide-react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Logo } from "./Logo";

export function AppShell({ fullBleed = false }: { fullBleed?: boolean }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const links =
    user?.role === "organizer"
      ? [
          { to: "/org", label: "Rounds", end: false },
        ]
      : [{ to: "/judge", label: "My reviews", end: true }];

  return (
    <div className={clsx("flex min-h-screen flex-col", fullBleed && "h-screen")}>
      <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur">
        <div className={clsx("flex h-14 items-center gap-6", fullBleed ? "px-4" : "mx-auto max-w-[1320px] px-6")}>
          <Link to={user?.role === "organizer" ? "/org" : "/judge"} className="shrink-0">
            <Logo />
          </Link>
          <nav className="flex items-center gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  clsx(
                    "rounded-md px-2.5 py-1.5 text-[13.5px] font-medium transition-colors",
                    isActive ? "bg-sunken text-ink" : "text-muted hover:text-ink",
                  )
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden rounded-md border border-line px-2 py-0.5 text-[11.5px] font-medium capitalize text-muted sm:inline">
              {user?.role}
            </span>
            <div className="hidden text-right leading-tight sm:block">
              <div className="text-[13px] font-medium text-ink">{user?.name}</div>
              <div className="text-[11.5px] text-muted">{user?.organization}</div>
            </div>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-navy text-[12px] font-semibold text-white">
              {user?.name
                .split(" ")
                .map((p) => p[0])
                .slice(0, 2)
                .join("")}
            </div>
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="rounded-md p-1.5 text-muted hover:bg-sunken hover:text-ink"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>
      <main className={clsx("flex-1", fullBleed ? "min-h-0" : "mx-auto w-full max-w-[1320px] px-6 py-8")}>
        <Outlet />
      </main>
    </div>
  );
}
