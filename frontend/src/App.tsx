import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { DemoStarting, DemoUnavailable } from "./components/DemoMode";
import { LoadingBlock } from "./components/ui";
import { DEMO_MODE } from "./lib/api";
import { useAuth } from "./lib/auth";
import type { Role } from "./lib/types";
import JudgeDashboard from "./pages/judge/JudgeDashboard";
import ReviewScreen from "./pages/judge/ReviewScreen";
import OrgHome from "./pages/organizer/OrgHome";
import RoundCreate from "./pages/organizer/RoundCreate";
import RoundLayout from "./pages/organizer/RoundLayout";
import RoundOverview from "./pages/organizer/RoundOverview";
import RoundSubmissions from "./pages/organizer/RoundSubmissions";
import RoundAssignments from "./pages/organizer/RoundAssignments";
import RoundResults from "./pages/organizer/RoundResults";
import RoundAudit from "./pages/organizer/RoundAudit";
import RoundSettings from "./pages/organizer/RoundSettings";
import SubmissionDetailPage from "./pages/organizer/SubmissionDetail";
import Landing from "./pages/public/Landing";
import Login from "./pages/public/Login";

function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return DEMO_MODE ? <DemoStarting /> : <LoadingBlock />;
  if (!user && DEMO_MODE) return <DemoUnavailable />;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (user.role !== role) return <Navigate to={user.role === "organizer" ? "/org" : "/judge"} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      {/* Public demo skips the landing page and opens the judge dashboard; the landing page stays at /about. */}
      <Route path="/" element={DEMO_MODE ? <Navigate to="/judge" replace /> : <Landing />} />
      <Route path="/about" element={<Landing />} />
      <Route path="/login" element={<Login />} />

      <Route element={<RequireRole role="organizer"><AppShell /></RequireRole>}>
        <Route path="/org" element={<OrgHome />} />
        <Route path="/org/rounds/new" element={<RoundCreate />} />
        <Route path="/org/rounds/:roundId" element={<RoundLayout />}>
          <Route index element={<RoundOverview />} />
          <Route path="submissions" element={<RoundSubmissions />} />
          <Route path="assignments" element={<RoundAssignments />} />
          <Route path="results" element={<RoundResults />} />
          <Route path="audit" element={<RoundAudit />} />
          <Route path="settings" element={<RoundSettings />} />
        </Route>
        <Route path="/org/submissions/:submissionId" element={<SubmissionDetailPage />} />
      </Route>

      <Route element={<RequireRole role="judge"><AppShell /></RequireRole>}>
        <Route path="/judge" element={<JudgeDashboard />} />
      </Route>
      <Route element={<RequireRole role="judge"><AppShell fullBleed /></RequireRole>}>
        <Route path="/judge/review/:assignmentId" element={<ReviewScreen />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
