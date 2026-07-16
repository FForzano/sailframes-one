import { Capacitor } from "@capacitor/core";
import { SecureStorage } from "@aparajita/capacitor-secure-storage";
import { setNativeRefreshSink, setRefreshTokenProvider } from "@/api/client";
import type { LoginResponse } from "@/services/auth";

// Native-only refresh-token handling. A Capacitor WebView's cookie jar
// doesn't survive cross-origin requests reliably (especially iOS), so
// `sf_refresh` (httpOnly cookie, used by the web app) doesn't work here —
// instead the refresh token travels in the /auth/login and /auth/refresh
// response bodies and is persisted in Keychain/Keystore-backed secure
// storage (never `@capacitor/preferences`, which is unencrypted, and never
// localStorage). The web bundle never imports this module.
const REFRESH_TOKEN_KEY = "sf_native_refresh_token";

let cachedRefreshToken: string | null = null;

/** Call once at native app startup (before the first authenticated
 * request), e.g. from a top-level native-only bootstrap effect. */
export async function initNativeAuth(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  cachedRefreshToken = (await SecureStorage.getItem(REFRESH_TOKEN_KEY)) as string | null;
  setRefreshTokenProvider(() => cachedRefreshToken);
  setNativeRefreshSink((token) => {
    cachedRefreshToken = token;
    void SecureStorage.setItem(REFRESH_TOKEN_KEY, token);
  });
}

/** Call after a successful authService.login() on native, to persist the
 * refresh token the same way rotation does on subsequent /auth/refresh
 * calls. */
export async function persistNativeLogin(login: LoginResponse): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  cachedRefreshToken = login.refresh_token;
  await SecureStorage.setItem(REFRESH_TOKEN_KEY, login.refresh_token);
}

/** Call from AuthContext.logout() on native, alongside the existing
 * setAccessToken(null), to drop the persisted refresh token too. */
export async function clearNativeAuth(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  cachedRefreshToken = null;
  await SecureStorage.removeItem(REFRESH_TOKEN_KEY);
}

/** The refresh token to send in the /auth/logout body (native has no
 * cookie to rely on) — `null` once initNativeAuth() hasn't run yet or on
 * web, where the caller should omit it entirely. */
export function getNativeRefreshToken(): string | null {
  return cachedRefreshToken;
}
