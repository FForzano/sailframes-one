// Framework-free domain types — designed to lift into a shared package when the
// native app is built. Mirrors the backend `web/api/domain` + `schemas`.

export interface User {
  id: number;
  email: string;
  name: string | null;
  is_active: boolean;
  is_superadmin: boolean;
  created_at?: string | null;
}

export interface LoginResponse {
  user: User;
  csrf_token: string;
}
