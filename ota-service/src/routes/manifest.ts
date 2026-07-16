import { Router } from "express";
import { getManifestJson, presignBundleUrl } from "../minio.js";

// Manifest schema maintained by scripts/deploy-ota.sh:
//   { "version": "1.4.0", "checksum": "<sha256 of the bundle zip>" }
// The bundle's actual download URL is NOT stored in the manifest — it's
// minted fresh (presigned, short-lived) on every request below, so it never
// goes stale even if a bundle is re-uploaded.
interface StoredManifest {
  version: string;
  checksum: string;
}

// NOTE: this implements the self-hosted update-check contract as documented
// for @capgo/capacitor-updater at the time this was written (POST body with
// the client's current version, JSON response with `version`/`url`/
// `checksum`, or an empty-ish response meaning "already current"). That
// plugin's self-hosted API has changed across releases — verify this against
// the live docs (capgo.app/docs/plugins/updater/self-hosted) and the pinned
// plugin version in frontend/package.json before relying on this in
// production; adjust field names here if they've drifted.
interface UpdateCheckRequest {
  version?: string;
  version_build?: string;
  [key: string]: unknown;
}

export const manifestRouter = Router();

manifestRouter.post("/manifest.json", async (req, res) => {
  const body = req.body as UpdateCheckRequest;
  const clientVersion = body.version ?? body.version_build ?? null;

  const raw = await getManifestJson();
  if (!raw) return res.json({}); // no release published yet — nothing to offer

  const manifest = JSON.parse(raw) as StoredManifest;
  if (manifest.version === clientVersion) {
    return res.json({}); // client is already current
  }

  const url = await presignBundleUrl(manifest.version);
  res.json({ version: manifest.version, url, checksum: manifest.checksum });
});

// Some plugin versions/manual testing use GET — same handler, no client
// version to compare against so it always returns the latest release.
manifestRouter.get("/manifest.json", async (_req, res) => {
  const raw = await getManifestJson();
  if (!raw) return res.json({});
  const manifest = JSON.parse(raw) as StoredManifest;
  const url = await presignBundleUrl(manifest.version);
  res.json({ version: manifest.version, url, checksum: manifest.checksum });
});
