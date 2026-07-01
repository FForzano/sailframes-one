import { Routes, Route } from "react-router-dom";
import { MainContent } from "@/components/layout/MainContent";
import { RequireAuth } from "@/utils/IsAuth";
import {
  requireBoatManager,
  requireEventsAccess,
  requireAdminArea,
} from "@/utils/guards";
import { Home } from "@/pages/Home";
import { Login } from "@/pages/Login";
import { Register } from "@/pages/Register";
import { NotFound } from "@/pages/NotFound";
import { Placeholder } from "@/pages/Placeholder";
import { Dashboard } from "@/pages/app/Dashboard";
import { RacesBrowser } from "@/pages/public/RacesBrowser";
import { RegattaDetail } from "@/pages/public/RegattaDetail";
import { FleetStatus } from "@/pages/public/FleetStatus";
import { Sessions } from "@/pages/public/Sessions";
import { SessionView } from "@/pages/public/SessionView";

// Route table. Every route renders inside MainContent (the layout orchestrator,
// which swaps Navbar/Sidebar/ActionBar by route + screen size). Personal-area
// routes are wrapped in RequireAuth; capability-scoped ones also carry a guard
// that mirrors the backend permission gate. Real feature pages replace the
// Placeholders across milestones M1–M5.
export default function App() {
  return (
    <Routes>
      <Route element={<MainContent />}>
        {/* Public */}
        <Route index element={<Home />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="races" element={<RacesBrowser />} />
        <Route path="races/:regattaId" element={<RegattaDetail />} />
        {/* The full race replay dashboard is M4; the link target exists now. */}
        <Route path="race/:raceId" element={<Placeholder titleKey="races.dashboardSoon" />} />
        <Route path="fleet" element={<FleetStatus />} />
        <Route path="sessions" element={<Sessions />} />
        <Route path="session/:deviceId/:date" element={<SessionView />} />

        {/* Personal area — single capability-aware shell */}
        <Route
          path="app"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="app/sessions"
          element={
            <RequireAuth>
              <Placeholder titleKey="nav.mySessions" />
            </RequireAuth>
          }
        />
        <Route
          path="app/boats"
          element={
            <RequireAuth>
              <Placeholder titleKey="nav.boats" />
            </RequireAuth>
          }
        />
        <Route
          path="app/clubs"
          element={
            <RequireAuth>
              <Placeholder titleKey="nav.clubs" />
            </RequireAuth>
          }
        />
        <Route
          path="app/groups"
          element={
            <RequireAuth>
              <Placeholder titleKey="nav.groups" />
            </RequireAuth>
          }
        />
        <Route
          path="app/devices"
          element={
            <RequireAuth guard={requireBoatManager}>
              <Placeholder titleKey="nav.devices" />
            </RequireAuth>
          }
        />
        <Route
          path="app/events"
          element={
            <RequireAuth guard={requireEventsAccess}>
              <Placeholder titleKey="nav.events" />
            </RequireAuth>
          }
        />
        <Route
          path="app/admin"
          element={
            <RequireAuth guard={requireAdminArea}>
              <Placeholder titleKey="nav.admin" />
            </RequireAuth>
          }
        />
        <Route
          path="app/profile"
          element={
            <RequireAuth>
              <Placeholder titleKey="nav.profile" />
            </RequireAuth>
          }
        />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
