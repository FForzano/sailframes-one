import { api } from "@/utils/api";

export interface CleanupPreview {
  dry_run: boolean;
  to_delete: Array<{
    device_id: string;
    date: string;
    duration_minutes: number;
    boat?: string | null;
    name?: string | null;
    reason?: string;
  }>;
  kept?: unknown[];
  deleted_count?: number;
}

// Bulk session cleanup (admin). dry_run defaults true server-side; we pass it
// explicitly so "preview" vs "delete" is unambiguous.
export const adminService = {
  cleanupSessions: (opts: {
    maxDurationMinutes: number;
    requireBoat: boolean;
    dryRun: boolean;
  }) => {
    const qs = new URLSearchParams({
      max_duration_minutes: String(opts.maxDurationMinutes),
      require_boat: String(opts.requireBoat),
      dry_run: String(opts.dryRun),
    });
    return api.post<CleanupPreview>(`/sessions/cleanup?${qs}`);
  },
};
