import { api, ApiError } from "@/utils/api";
import { CSRF_COOKIE, CSRF_HEADER, readCookie } from "@/utils/csrf";
import type { SessionDetail, SessionSummary, Visibility } from "@/types";

export interface CrewSlot {
  user_id?: number | null;
  guest_name?: string | null;
  boat_role?: string | null;
}

export interface SessionCrewEdit {
  crew: CrewSlot[];
  boat_id?: string;
  visibility?: Visibility;
  club_id?: number;
  group_id?: number;
}

export interface SessionCreate {
  boat_id: string;
  date: string;
  device_id?: string | null;
  name?: string;
  crew: CrewSlot[];
}

interface GpxUploadUrl {
  url: string;
  key: string;
  method: string;
}

const GPX_CONTENT_TYPE = "application/gpx+xml";

export const sessionsService = {
  // Server filters by visibility — anonymous callers get only public sessions.
  list: () =>
    api
      .get<{ sessions: SessionSummary[] }>("/sessions")
      .then((r) => r.sessions),

  // 404 for a private session the caller can't see (never confirmed to exist).
  get: (deviceId: string, date: string) =>
    api.get<SessionDetail>(`/sessions/${deviceId}/${date}`),

  // The only way to address a manual (device-less) session.
  getById: (id: number) => api.get<SessionDetail>(`/sessions/id/${id}`),

  create: (body: SessionCreate) => api.post<SessionDetail>("/sessions", body),

  editCrew: (deviceId: string, date: string, body: SessionCrewEdit) =>
    api.patch<SessionDetail>(`/sessions/${deviceId}/${date}/crew`, body),

  // Backend gates deletion on require_admin / session.delete.
  remove: (deviceId: string, date: string) =>
    api.del<{ status: string }>(`/sessions/${deviceId}/${date}`),

  // --- Manual session GPX upload (S3-signed-URL-style) ---

  getGpxUploadUrl: (id: number) =>
    api.post<GpxUploadUrl>(`/sessions/${id}/gpx/upload-url`),

  completeGpxUpload: (id: number) =>
    api.post<{ status: string; id: number }>(`/sessions/${id}/gpx/complete`),

  // Uploads the raw file straight to the target (S3 presigned PUT, or the
  // `/api/uploads` proxy on MinIO/local) — bypasses `api.ts`, which always
  // JSON-encodes the body. A same-origin proxy path gets cookie auth + the
  // CSRF header like every other mutation; an absolute presigned URL is
  // cross-origin (S3) and carries its own auth in the query string.
  uploadGpxFile: async (uploadUrl: string, file: File | Blob) => {
    const sameOrigin = uploadUrl.startsWith("/");
    const res = await fetch(uploadUrl, {
      method: "PUT",
      body: file,
      headers: {
        "Content-Type": GPX_CONTENT_TYPE,
        ...(sameOrigin ? { [CSRF_HEADER]: readCookie(CSRF_COOKIE) ?? "" } : {}),
      },
      credentials: sameOrigin ? "include" : "omit",
    });
    if (!res.ok) {
      throw new ApiError(res.status, await res.text().catch(() => null));
    }
  },
};
