import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Capacitor } from "@capacitor/core";
import { ApiError, AUTH_EXPIRED_EVENT, setAccessToken } from "@/api/client";
import { authService } from "@/services/auth";
import type { Capabilities, User } from "@/types";

// Dynamic import: keeps @aparajita/capacitor-secure-storage out of the web
// bundle entirely (see services/nativeAuth.ts) — this module is only ever
// touched when actually running inside the native shell.
const nativeAuth = () => import("@/services/nativeAuth");

export type AuthStatus = "loading" | "authed" | "anon";

export interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  caps: Capabilities | null;
  login: (email: string, password: string) => Promise<void>;
  register: (body: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    terms_and_conditions: boolean;
    privacy_policy: boolean;
  }) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-fetch capabilities after membership/role-changing mutations. */
  refreshCaps: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const queryClient = useQueryClient();

  const loadIdentity = useCallback(async () => {
    try {
      const c = await authService.capabilities();
      setCaps(c);
      setStatus("authed");
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        setCaps(null);
        setStatus("anon");
      } else {
        // Network/server error: stay anon but don't wipe a valid session's
        // cookie state — a reload retries.
        setCaps(null);
        setStatus("anon");
      }
    }
  }, []);

  useEffect(() => {
    // Loads the persisted native refresh token (if any) before the first
    // capabilities call, so a returning native user doesn't have to log in
    // again — a no-op on web.
    const init = Capacitor.isNativePlatform()
      ? nativeAuth().then((m) => m.initNativeAuth())
      : Promise.resolve();
    void init.then(loadIdentity);
  }, [loadIdentity]);

  // The api client dispatches this when a refresh attempt fails.
  useEffect(() => {
    const onExpired = () => {
      setAccessToken(null);
      setCaps(null);
      setStatus("anon");
      queryClient.clear();
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [queryClient]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await authService.login(email, password);
      if (Capacitor.isNativePlatform()) {
        await (await nativeAuth()).persistNativeLogin(res);
      }
      await loadIdentity();
    },
    [loadIdentity],
  );

  const register = useCallback(
    async (body: Parameters<AuthContextValue["register"]>[0]) => {
      await authService.register(body);
      await login(body.email, body.password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      if (Capacitor.isNativePlatform()) {
        const m = await nativeAuth();
        await authService.logout(m.getNativeRefreshToken() ?? undefined);
        await m.clearNativeAuth();
      } else {
        await authService.logout();
      }
    } finally {
      setAccessToken(null);
      setCaps(null);
      setStatus("anon");
      queryClient.clear();
    }
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: caps?.user ?? null,
      caps,
      login,
      register,
      logout,
      refreshCaps: loadIdentity,
    }),
    [status, caps, login, register, logout, loadIdentity],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
