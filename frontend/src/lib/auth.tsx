import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { DEMO_MODE, api, getToken, setToken } from "./api";
import type { User } from "./types";

export type DemoRole = "judge" | "organizer";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  /** Password-less guest sign-in (public demo only). */
  demoLogin: (role: DemoRole) => Promise<User>;
  /** Set when the automatic guest sign-in could not reach the demo server. */
  demoError: string | null;
  retryDemo: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const DEMO_ATTEMPTS = 4;
const DEMO_RETRY_MS = 4000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(getToken()) || DEMO_MODE);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [demoAttempt, setDemoAttempt] = useState(0);

  const demoLogin = useCallback(async (role: DemoRole) => {
    const res = await api<{ token: string; user: User }>("/api/auth/demo", { method: "POST", json: { role } });
    setToken(res.token);
    setUser(res.user);
    return res.user;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function guestSignIn() {
      // A sleeping free-tier backend can take ~a minute to wake; retry a few times.
      for (let i = 1; i <= DEMO_ATTEMPTS && !cancelled; i++) {
        try {
          await demoLogin("judge");
          return;
        } catch (err) {
          if (i === DEMO_ATTEMPTS) throw err;
          await new Promise((r) => setTimeout(r, DEMO_RETRY_MS));
        }
      }
    }

    async function restore() {
      setDemoError(null);
      if (getToken()) {
        try {
          const me = await api<User>("/api/auth/me");
          if (!cancelled) setUser(me);
          return;
        } catch {
          // Expired or from a previous (reseeded) demo instance — fall through.
          setToken(null);
        }
      }
      if (DEMO_MODE && !cancelled) {
        try {
          await guestSignIn();
        } catch {
          if (!cancelled) setDemoError("The demo server didn't respond. It may still be waking up.");
        }
      }
    }

    void restore().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [demoLogin, demoAttempt]);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener("evidra:unauthorized", onUnauthorized);
    return () => window.removeEventListener("evidra:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ token: string; user: User }>("/api/auth/login", { method: "POST", json: { email, password } });
    setToken(res.token);
    setUser(res.user);
    return res.user;
  }, []);

  const retryDemo = useCallback(() => {
    setLoading(true);
    setDemoAttempt((n) => n + 1);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, demoLogin, demoError, retryDemo, logout }),
    [user, loading, login, demoLogin, demoError, retryDemo, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
