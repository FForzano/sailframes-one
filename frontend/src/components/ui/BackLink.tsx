import { Link, useLocation, useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import styles from "./BackLink.module.css";

/** Explicit "back" affordance for detail pages — the app has no visible
 * browser chrome on mobile, so this can't rely on the browser's back button
 * alone. Pass exactly one of:
 * - `to`: a fixed destination, for pages with exactly one true logical
 *   parent regardless of how you got there (e.g. a club/group detail page
 *   always goes back to its list).
 * - `fallback`: pages reachable from several different lists (an activity
 *   from the personal feed, a club's feed, or that club's own Eventi tab)
 *   go back to wherever the user actually came from (`navigate(-1)`), only
 *   falling back to a fixed URL when there's no in-app history to unwind
 *   (e.g. the page was opened directly via a deep link). React Router marks
 *   the initial history entry's `location.key` as `"default"`. */
export function BackLink({ to, fallback, label }: { label: string; to?: string; fallback?: string }) {
  const navigate = useNavigate();
  const location = useLocation();

  if (to) {
    return (
      <Link to={to} className={styles.backlink}>
        <ChevronLeft size={16} />
        {label}
      </Link>
    );
  }

  return (
    <button
      type="button"
      className={styles.backlink}
      onClick={() =>
        location.key !== "default" ? navigate(-1) : navigate(fallback ?? "/", { replace: true })
      }
    >
      <ChevronLeft size={16} />
      {label}
    </button>
  );
}
