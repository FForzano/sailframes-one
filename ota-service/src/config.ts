// Reuses the SAME env var names as backend/storage/object_store.py — this
// service is a separate process but points at the same MinIO instance/
// bucket, just a different key prefix, so there's no reason to invent new
// credential var names.
function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

function endpointParts(url: string): { host: string; port: number; useSSL: boolean } {
  const u = new URL(url);
  return {
    host: u.hostname,
    port: u.port ? Number(u.port) : u.protocol === "https:" ? 443 : 80,
    useSSL: u.protocol === "https:",
  };
}

export const config = {
  port: Number(process.env.OTA_PORT ?? 8081),
  bucket: process.env.SAILFRAMES_BUCKET ?? "sailframes-fleet-data-prod",
  // Key prefix within the shared bucket, e.g. app-updates/manifest.json,
  // app-updates/bundles/{version}.zip. New, OTA-specific — everything else
  // below reuses backend/storage/object_store.py's exact var names.
  otaPrefix: process.env.SAILFRAMES_OTA_PREFIX ?? "app-updates",
  minio: endpointParts(process.env.SAILFRAMES_S3_ENDPOINT ?? "http://minio:9000"),
  accessKey: required("MINIO_ROOT_USER"),
  secretKey: required("MINIO_ROOT_PASSWORD"),
  // Presigned bundle URLs expire quickly — clients fetch and re-download
  // immediately, no reason to keep them valid longer.
  presignExpirySeconds: 300,
};
