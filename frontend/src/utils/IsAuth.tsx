import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useCapabilities } from "@/hooks/useCapabilities";
import type { Guard } from "./guards";
import { Spinner } from "@/components/ui/Spinner";

// Route protection. `RequireAuth` gates on authentication (+ optional capability
// guard); while identity is loading it renders a spinner rather than flashing
// the login page. Anonymous users are redirected to /login?redirect=<path>.
export function RequireAuth({
  children,
  guard,
}: {
  children: React.ReactNode;
  guard?: Guard;
}) {
  const { status } = useAuth();
  const caps = useCapabilities();
  const location = useLocation();

  if (status === "loading") return <Spinner full />;

  if (status === "anon") {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (guard && !guard(caps)) {
    // Authenticated but lacks the capability — bounce to the personal home.
    return <Navigate to="/app" replace />;
  }

  return <>{children}</>;
}
