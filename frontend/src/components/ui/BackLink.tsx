import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

/** Explicit "back to list" affordance for detail pages reached from a list
 * (club/group detail → their list) — the app has no visible browser chrome
 * on mobile, so this can't rely on the browser's back button alone. */
export function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} className="sf-backlink">
      <ChevronLeft size={16} />
      {label}
    </Link>
  );
}
