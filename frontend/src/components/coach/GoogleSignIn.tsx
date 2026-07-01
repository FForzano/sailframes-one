import { useEffect, useRef } from "react";
import { COACH_CLIENT_ID } from "@/services/coach.service";

// Minimal Google Identity Services button. Loads the GIS script once, then
// renders the official button; on credential it calls back with the ID token.
// Isolated to the coach area — the member app never touches Google auth.
interface GsiCredential {
  credential: string;
}
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: { client_id: string; callback: (r: GsiCredential) => void }) => void;
          renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const SRC = "https://accounts.google.com/gsi/client";

export function GoogleSignIn({ onCredential }: { onCredential: (idToken: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!COACH_CLIENT_ID) return;
    let cancelled = false;

    const render = () => {
      if (cancelled || !ref.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: COACH_CLIENT_ID,
        callback: (r) => r.credential && onCredential(r.credential),
      });
      window.google.accounts.id.renderButton(ref.current, { theme: "filled_black", size: "large" });
    };

    if (window.google) {
      render();
    } else {
      const existing = document.querySelector<HTMLScriptElement>(`script[src="${SRC}"]`);
      if (existing) {
        existing.addEventListener("load", render);
      } else {
        const s = document.createElement("script");
        s.src = SRC;
        s.async = true;
        s.defer = true;
        s.onload = render;
        document.head.appendChild(s);
      }
    }
    return () => {
      cancelled = true;
    };
  }, [onCredential]);

  if (!COACH_CLIENT_ID) {
    return <p className="sf-muted">VITE_GOOGLE_CLIENT_ID not configured.</p>;
  }
  return <div ref={ref} />;
}
