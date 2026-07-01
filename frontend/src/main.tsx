import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./i18n";
import "./styles/global.css";
import { LoadingProvider } from "@/contexts/LoadingContext";
import { ErrorProvider } from "@/contexts/ErrorContext";
import { ToastProvider } from "@/contexts/ToastContext";
import { AuthProvider } from "@/contexts/AuthContext";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

// Provider order: Loading/Error/Toast are leaf infra Auth may use; Auth wraps
// the app so identity + capabilities are available everywhere; Router is
// outermost so route-aware hooks work inside AuthProvider too.
createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <LoadingProvider>
        <ErrorProvider>
          <ToastProvider>
            <AuthProvider>
              <App />
            </AuthProvider>
          </ToastProvider>
        </ErrorProvider>
      </LoadingProvider>
    </BrowserRouter>
  </StrictMode>,
);
