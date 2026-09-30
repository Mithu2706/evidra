import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Gavel, LayoutDashboard } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "../../components/Logo";
import { Button, Callout } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { User } from "../../lib/types";

const DEMO_NOTES: Record<string, string> = {
  "marcus@demo.evidra.app": "Four fresh assignments — best for walking the judge flow",
  "elena@demo.evidra.app": "Completed reviews, including a revision after AI reveal",
  "sam@demo.evidra.app": "One completed, one in progress",
  "dana@demo.evidra.app": "Round setup, uploads, assignments, progress, results, audit",
};

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const demo = useQuery({ queryKey: ["demo-accounts"], queryFn: () => api<{ accounts: User[]; password: string | null }>("/api/auth/demo-accounts") });

  useEffect(() => {
    if (user) navigate(user.role === "organizer" ? "/org" : "/judge", { replace: true });
  }, [user, navigate]);

  async function signIn(e: string, p: string) {
    setBusy(e);
    setError(null);
    try {
      const u = await login(e, p);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from.startsWith(u.role === "organizer" ? "/org" : "/judge") ? from : u.role === "organizer" ? "/org" : "/judge");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void signIn(email, password);
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col px-8 py-8 sm:px-14">
        <Link to="/">
          <Logo />
        </Link>
        <div className="my-auto w-full max-w-sm py-12">
          <h1 className="text-[24px] font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-[14px] text-muted">Organizers and judges use the same sign-in.</p>
          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && <Callout tone="danger">{error}</Callout>}
            <Button type="submit" variant="primary" size="lg" className="w-full" loading={busy === email && !!email}>
              Sign in
            </Button>
          </form>
        </div>
        <p className="text-[12px] text-faint">Evidra supports human judges. It does not make decisions.</p>
      </div>

      <div className="hidden border-l border-line bg-surface lg:flex lg:flex-col lg:justify-center lg:px-14">
        {demo.data && demo.data.accounts.length > 0 && (
          <div className="max-w-md">
            <div className="eyebrow">Demo workspace</div>
            <h2 className="mt-1 text-[18px] font-semibold">Northbridge Innovation Network</h2>
            <p className="mt-1 text-[13.5px] text-muted">
              A fictional round with six sample pitch decks. Choose an account to explore — password <code className="rounded bg-sunken px-1 font-mono text-[12px]">{demo.data.password}</code>.
            </p>
            <div className="mt-6 space-y-2">
              {demo.data.accounts.map((a) => (
                <button
                  key={a.id}
                  onClick={() => void signIn(a.email, demo.data!.password!)}
                  disabled={busy !== null}
                  className="group flex w-full items-center gap-3 rounded-xl border border-line bg-canvas px-4 py-3 text-left transition-all hover:border-line-strong hover:bg-surface hover:shadow-card"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface text-muted ring-1 ring-line">
                    {a.role === "organizer" ? <LayoutDashboard className="h-4 w-4" /> : <Gavel className="h-4 w-4" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2 text-[13.5px] font-medium text-ink">
                      {a.name} <span className="rounded border border-line px-1 text-[10.5px] font-medium capitalize text-muted">{a.role}</span>
                    </span>
                    <span className="block truncate text-[12px] text-muted">{DEMO_NOTES[a.email] ?? a.title}</span>
                  </span>
                  <ArrowRight className="h-4 w-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-ink" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
