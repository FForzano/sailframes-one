import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Dev server proxies /api to the FastAPI backend so cookies stay first-party
// (the browser only ever talks to :5173). Run the backend with
// SAILFRAMES_COOKIE_SECURE=0 so cookies are set over plain http in dev.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: true },
  base: "/",
});
