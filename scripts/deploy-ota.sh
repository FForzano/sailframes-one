#!/usr/bin/env bash
# Publish a new OTA update for the XGSail native app: build the frontend for
# the native target, zip it, upload to MinIO, and refresh the manifest that
# ota-service/ serves.
#
# Only ever ships JS/HTML/CSS/assets (the `frontend/dist` build output) —
# never android/, ios/, or capacitor.config.ts. That split is what keeps
# these updates App-Store-compliant; see docs/ota-updates.md.
#
# Usage:
#   OTA_API_BASE=https://api.xgsail.com/api \
#   SAILFRAMES_S3_ENDPOINT=http://localhost:9000 \
#   MINIO_ROOT_USER=sailframes MINIO_ROOT_PASSWORD=... \
#   SAILFRAMES_BUCKET=sailframes-fleet-data-prod \
#   scripts/deploy-ota.sh [VERSION]
#
# VERSION defaults to `git describe --tags --always` in frontend/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${OTA_API_BASE:?set OTA_API_BASE to the deployed backend origin, e.g. https://api.xgsail.com/api}"
: "${SAILFRAMES_S3_ENDPOINT:?set SAILFRAMES_S3_ENDPOINT, e.g. http://localhost:9000}"
: "${MINIO_ROOT_USER:?set MINIO_ROOT_USER}"
: "${MINIO_ROOT_PASSWORD:?set MINIO_ROOT_PASSWORD}"
BUCKET="${SAILFRAMES_BUCKET:-sailframes-fleet-data-prod}"
OTA_PREFIX="${SAILFRAMES_OTA_PREFIX:-app-updates}"
VERSION="${1:-$(cd "$ROOT/frontend" && git describe --tags --always)}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "==> building frontend (native target, VITE_API_BASE=$OTA_API_BASE) for version $VERSION"
( cd "$ROOT/frontend" && VITE_API_BASE="$OTA_API_BASE" npm run build )

echo "==> zipping dist/"
( cd "$ROOT/frontend/dist" && zip -qr "$WORKDIR/bundle.zip" . )

CHECKSUM="$(shasum -a 256 "$WORKDIR/bundle.zip" | cut -d' ' -f1)"
cat > "$WORKDIR/manifest.json" <<EOF
{"version": "$VERSION", "checksum": "$CHECKSUM"}
EOF

echo "==> uploading bundle + manifest to MinIO (local/$BUCKET/$OTA_PREFIX)"
mc alias set ota-deploy "$SAILFRAMES_S3_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc cp "$WORKDIR/bundle.zip" "ota-deploy/$BUCKET/$OTA_PREFIX/bundles/$VERSION.zip"
mc cp "$WORKDIR/manifest.json" "ota-deploy/$BUCKET/$OTA_PREFIX/manifest.json"

echo "==> done: version $VERSION published (checksum $CHECKSUM)"
