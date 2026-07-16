import express from "express";
import cors from "cors";
import { config } from "./config.js";
import { manifestRouter } from "./routes/manifest.js";
import { bundleRouter } from "./routes/bundle.js";

// Standalone OTA update server — no auth, no database, no dependency on the
// FastAPI backend. Public/read-only by design: it only ever hands out JS
// bundle download URLs, the same trust level as the existing firmware/*
// anonymous-read prefix in deploy/minio-init.sh.
const app = express();
app.use(cors());
app.use(express.json());

app.get("/health", (_req, res) => res.status(200).json({ ok: true }));
app.use(manifestRouter);
app.use(bundleRouter);

app.listen(config.port, () => {
  console.log(`ota-service listening on :${config.port}`);
});
