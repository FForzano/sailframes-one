import type { SessionStatus } from "@/types";

export function sessionStatusBadge(status: SessionStatus): string {
  return status === "processed"
    ? "sf-badge sf-badge--success"
    : status === "failed"
      ? "sf-badge sf-badge--danger"
      : "sf-badge sf-badge--warning";
}
