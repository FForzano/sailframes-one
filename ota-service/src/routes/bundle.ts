import { Router } from "express";
import { bundleExists, presignBundleUrl } from "../minio.js";

// GET /bundle/:version -> 302 to a short-lived presigned MinIO URL, so large
// zip bundles never flow through this service's own process — mirrors
// backend/storage/object_store.py's presigned-URL-over-proxying philosophy.
export const bundleRouter = Router();

bundleRouter.get("/bundle/:version", async (req, res) => {
  const { version } = req.params;
  if (!(await bundleExists(version))) {
    return res.status(404).json({ error: "No bundle for that version" });
  }
  res.redirect(302, await presignBundleUrl(version));
});
