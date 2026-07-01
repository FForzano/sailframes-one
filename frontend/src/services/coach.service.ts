// Coach app client — DELIBERATELY separate from the member cookie auth.
// The coach backend is its own service (VITE_COACH_API_BASE, a Lambda) using
// Google Sign-In → a 30-day session token held in localStorage and sent as a
// Bearer header. We do not unify it with the member session (see the refactor
// plan's note); this file is the whole seam.
const BASE = (import.meta.env.VITE_COACH_API_BASE ?? "").replace(/\/+$/, "");
export const COACH_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

const TOKEN_KEY = "sf-coach-id-token";
const EMAIL_KEY = "sf-coach-email";

export interface Briefing {
  race_id: string;
  device_id: string;
  boat_name?: string;
  race_name?: string;
  created_at?: string;
  [key: string]: unknown;
}

function decode(token: string): { email?: string; exp?: number } | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

export const coachService = {
  isConfigured: () => Boolean(BASE),
  getToken: () => localStorage.getItem(TOKEN_KEY),
  getEmail: () => localStorage.getItem(EMAIL_KEY),
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
  },

  // Valid = present and not within 30s of expiry.
  hasValidToken(): boolean {
    const t = this.getToken();
    if (!t) return false;
    const exp = decode(t)?.exp;
    return Boolean(exp && exp * 1000 > Date.now() + 30_000);
  },

  // Swap a Google ID token for the coach service session token (30-day).
  async exchange(googleIdToken: string, email: string) {
    const resp = await fetch(`${BASE}/session/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: googleIdToken, email }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.session_token) {
      throw new Error(`session/exchange HTTP ${resp.status}`);
    }
    localStorage.setItem(TOKEN_KEY, data.session_token);
    localStorage.setItem(EMAIL_KEY, email);
  },

  async api<T>(path: string, opts: RequestInit = {}): Promise<T> {
    if (!BASE) throw new Error("VITE_COACH_API_BASE not configured");
    const token = this.getToken();
    const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (opts.body) headers["Content-Type"] = "application/json";
    const resp = await fetch(BASE + path, { ...opts, headers });
    if (resp.status === 401) {
      this.clear();
      throw new Error("unauthorized");
    }
    const text = await resp.text();
    const data = text ? JSON.parse(text) : null;
    if (!resp.ok) throw new Error(`API ${resp.status}`);
    return data as T;
  },

  listBriefings: () =>
    coachService
      .api<{ briefings: Briefing[] }>("/briefings")
      .then((r) => r.briefings ?? []),
  generate: (raceId: string, deviceId: string) =>
    coachService.api<Briefing>("/generate", {
      method: "POST",
      body: JSON.stringify({ race_id: raceId, device_id: deviceId }),
    }),
};
