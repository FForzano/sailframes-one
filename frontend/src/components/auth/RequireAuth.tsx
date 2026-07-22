import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { Spinner } from "@/components/ui/Spinner";
import { LegalAcceptanceGate } from "@/components/auth/LegalAcceptanceGate";

/** Login-everywhere gate: the whole app shell lives under this route. */
export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <Spinner full />;
  if (status === "anon") {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  return <Outlet />;
}

/** Blocks the whole authed app behind (re-)acceptance of updated legal
 * documents. Sits just inside RequireAuth so only logged-in users hit it, and
 * above the app shell so the gate replaces the entire app until accepted. */
export function RequireLegalAcceptance() {
  const { caps } = useAuth();
  if (caps?.legal?.needsAcceptance) return <LegalAcceptanceGate />;
  return <Outlet />;
}

export function RequireSuperadmin() {
  const { user, status } = useAuth();
  if (status === "loading") return <Spinner full />;
  if (!user?.is_superadmin) return <Navigate to="/" replace />;
  return <Outlet />;
}
