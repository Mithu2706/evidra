import { useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { FlaskConical, RotateCw } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, type DemoRole } from "../lib/auth";
import { Logo } from "./Logo";
import { Button, Callout, Spinner } from "./ui";

export const DEMO_BANNER_TEXT = "Live demo with fictional data — AI analysis runs on the offline heuristic engine.";

export function DemoBanner() {
  return (
    <div className="flex items-center justify-center gap-2 bg-navy px-4 py-1.5 text-center text-[12px] text-white/90">
      <FlaskConical className="h-3.5 w-3.5 shrink-0" />
      <span>{DEMO_BANNER_TEXT}</span>
      <Link to="/about" className="hidden whitespace-nowrap font-medium text-white underline-offset-2 hover:underline sm:inline">
        About Evidra
      </Link>
    </div>
  );
}

const ROLES: { role: DemoRole; label: string; home: string }[] = [
  { role: "judge", label: "Judge", home: "/judge" },
  { role: "organizer", label: "Organizer", home: "/org" },
];

/** Lets visitors flip between the seeded demo judge and organizer without a password. */
export function DemoRoleSwitcher() {
  const { user, demoLogin } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<DemoRole | null>(null);

  async function switchTo(role: DemoRole, home: string) {
    if (busy || user?.role === role) return;
    setBusy(role);
    try {
      await demoLogin(role);
      qc.clear(); // cached data belongs to the previous account
      navigate(home);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="inline-flex rounded-lg border border-line bg-canvas p-0.5" role="group" aria-label="View the demo as">
      {ROLES.map(({ role, label, home }) => (
        <button
          key={role}
          onClick={() => void switchTo(role, home)}
          aria-pressed={user?.role === role}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors",
            user?.role === role ? "bg-surface text-ink shadow-card" : "text-muted hover:text-ink",
          )}
        >
          {busy === role && <Spinner />}
          {label}
        </button>
      ))}
    </div>
  );
}

/** Full-page state while the guest sign-in runs (the free-tier backend may be waking up). */
export function DemoStarting() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-canvas px-6 text-center">
      <Logo />
      <div className="flex items-center gap-2 text-[14px] text-ink-2">
        <Spinner /> Opening the live demo…
      </div>
      <p className="max-w-sm text-[12.5px] text-muted">
        On a first visit the demo server may need up to a minute to wake up. No sign-in is required.
      </p>
    </div>
  );
}

export function DemoUnavailable() {
  const { demoError, retryDemo } = useAuth();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-canvas px-6">
      <Logo />
      <div className="w-full max-w-md">
        <Callout tone="warn" title="The demo isn't reachable right now">
          {demoError ?? "The demo server didn't respond."} Please try again in a few seconds.
        </Callout>
      </div>
      <div className="flex gap-2">
        <Button variant="primary" icon={<RotateCw className="h-4 w-4" />} onClick={retryDemo}>
          Try again
        </Button>
        <Link to="/about">
          <Button variant="ghost">About Evidra</Button>
        </Link>
      </div>
    </div>
  );
}
