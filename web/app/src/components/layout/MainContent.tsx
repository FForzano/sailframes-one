import { Outlet, useLocation } from "react-router-dom";
import { useScreenWidth } from "@/hooks/useScreenWidth";
import { Navbar } from "./Navbar";
import { Sidebar } from "./Sidebar";
import { ActionBar } from "./ActionBar";
import { Footer } from "./Footer";
import { ToastViewport } from "@/components/ui/ToastViewport";

// Layout orchestrator (mirrors the reference app's MainContent): personal-area
// routes (/app/*) get the Sidebar on desktop and the bottom ActionBar on
// mobile/tablet; public routes get the top Navbar + Footer.
export function MainContent() {
  const location = useLocation();
  const { isDesktop } = useScreenWidth();
  const inApp = location.pathname === "/app" || location.pathname.startsWith("/app/");

  if (inApp) {
    return (
      <div className={isDesktop ? "sf-shell sf-shell--desktop" : "sf-shell sf-shell--compact"}>
        {isDesktop && <Sidebar />}
        <main className="sf-appmain">
          <Outlet />
        </main>
        {!isDesktop && <ActionBar />}
        <ToastViewport />
      </div>
    );
  }

  return (
    <div className="sf-public">
      <Navbar />
      <main className="sf-publicmain">
        <Outlet />
      </main>
      <Footer />
      <ToastViewport />
    </div>
  );
}
