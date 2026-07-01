import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { authService } from "@/services/auth.service";
import { ApiError, AUTH_EXPIRED_EVENT } from "@/utils/api";
import type { Capabilities, User } from "@/types";

type AuthStatus = "loading" | "authed" | "anon";

export interface AuthContextValue {
  user: User | null;
  caps: Capabilities | null;
  status: AuthStatus;
  isAuth: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-fetch identity + capabilities (after membership/role changes). */
  refresh: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const mounted = useRef(true);

  const loadIdentity = useCallback(async () => {
    try {
      const me = await authService.me();
      const capabilities = await authService.capabilities();
      if (!mounted.current) return;
      setUser(me);
      setCaps(capabilities);
      setStatus("authed");
    } catch (err) {
      if (!mounted.current) return;
      // 401 == anonymous; anything else we still treat as anon but keep going.
      if (!(err instanceof ApiError) || err.status === 401) {
        setUser(null);
        setCaps(null);
      }
      setStatus("anon");
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void loadIdentity();
    const onExpired = () => {
      setUser(null);
      setCaps(null);
      setStatus("anon");
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => {
      mounted.current = false;
      window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
    };
  }, [loadIdentity]);

  const login = useCallback(
    async (email: string, password: string) => {
      await authService.login(email, password);
      await loadIdentity();
    },
    [loadIdentity],
  );

  const register = useCallback(
    async (email: string, password: string, name?: string) => {
      await authService.register(email, password, name);
      await authService.login(email, password);
      await loadIdentity();
    },
    [loadIdentity],
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      setUser(null);
      setCaps(null);
      setStatus("anon");
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      caps,
      status,
      isAuth: status === "authed",
      login,
      register,
      logout,
      refresh: loadIdentity,
    }),
    [user, caps, status, login, register, logout, loadIdentity],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
