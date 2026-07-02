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
import { Dashboard } from "@/pages/app/Dashboard";
import { RacesBrowser } from "@/pages/public/RacesBrowser";
import { RegattaDetail } from "@/pages/public/RegattaDetail";
import { FleetStatus } from "@/pages/public/FleetStatus";
import { Sessions } from "@/pages/public/Sessions";
import { SessionView } from "@/pages/public/SessionView";
import { RaceView } from "@/pages/public/RaceView";
import { Bom } from "@/pages/public/Bom";
import { Battery } from "@/pages/public/Battery";
import { Clubs } from "@/pages/app/Clubs";
import { Groups } from "@/pages/app/Groups";
import { Boats } from "@/pages/app/Boats";
import { Devices } from "@/pages/app/Devices";
import { MySessions } from "@/pages/app/MySessions";
import { Profile } from "@/pages/app/Profile";
import { Events } from "@/pages/app/Events";
import { Admin } from "@/pages/app/Admin";

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
        <Route path="race/:raceId" element={<RaceView />} />
        <Route path="fleet" element={<FleetStatus />} />
        <Route path="sessions" element={<Sessions />} />
        <Route path="session/:deviceId/:date" element={<SessionView />} />
        <Route path="bom" element={<Bom />} />
        <Route path="battery" element={<Battery />} />

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
              <MySessions />
            </RequireAuth>
          }
        />
        <Route
          path="app/boats"
          element={
            <RequireAuth>
              <Boats />
            </RequireAuth>
          }
        />
        <Route
          path="app/clubs"
          element={
            <RequireAuth>
              <Clubs />
            </RequireAuth>
          }
        />
        <Route
          path="app/groups"
          element={
            <RequireAuth>
              <Groups />
            </RequireAuth>
          }
        />
        <Route
          path="app/devices"
          element={
            <RequireAuth guard={requireBoatManager}>
              <Devices />
            </RequireAuth>
          }
        />
        <Route
          path="app/events"
          element={
            <RequireAuth guard={requireEventsAccess}>
              <Events />
            </RequireAuth>
          }
        />
        <Route
          path="app/admin"
          element={
            <RequireAuth guard={requireAdminArea}>
              <Admin />
            </RequireAuth>
          }
        />
        <Route
          path="app/profile"
          element={
            <RequireAuth>
              <Profile />
            </RequireAuth>
          }
        />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
