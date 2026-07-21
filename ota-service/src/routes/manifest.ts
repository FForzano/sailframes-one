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
//
// `version_name` (not `version_build`!) is the currently-installed BUNDLE's
// version — the one that changes after applying an OTA update and is what
// must be compared against manifest.version. `version_build`/`version_code`
// are the native app's own (store-submitted) version, which never changes
// between OTA updates — comparing against it instead meant this endpoint
// always reported an update as available, even immediately after the client
// had just applied it, which looped the app on downloading and re-applying
// the same bundle forever. Confirmed against the installed plugin's request
// body (android/.../CapgoUpdater.java's createInfoObject()).
interface UpdateCheckRequest {
  version_name?: string;
  version?: string;
  version_build?: string;
  [key: string]: unknown;
}

export const manifestRouter = Router();

manifestRouter.post("/manifest.json", async (req, res) => {
  const body = req.body as UpdateCheckRequest;
  const clientVersion = body.version_name ?? body.version ?? body.version_build ?? null;

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
