#!/usr/bin/env bash
# Prune old xgsail image tags on Docker Hub so the repo doesn't grow
# unbounded. For each service, keeps the newest KEEP <service>-sha-* tags
# (by push date) and always keeps <service>-latest.
#
# Usage:
#   DOCKERHUB_USERNAME=... DOCKERHUB_TOKEN=... scripts/dockerhub-prune-tags.sh [KEEP]
set -euo pipefail

REPO="fforzano99/xgsail"
KEEP="${1:-10}"
SERVICES=(backend frontend process-upload video)

: "${DOCKERHUB_USERNAME:?DOCKERHUB_USERNAME is required}"
: "${DOCKERHUB_TOKEN:?DOCKERHUB_TOKEN is required}"

JWT="$(curl -sf -X POST "https://hub.docker.com/v2/users/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"${DOCKERHUB_USERNAME}\", \"password\": \"${DOCKERHUB_TOKEN}\"}" \
  | jq -r '.token')"

if [[ -z "$JWT" || "$JWT" == "null" ]]; then
  echo "Docker Hub login failed" >&2
  exit 1
fi

# Fetches every tag for $REPO across pages, as a stream of "<name> <tag_last_pushed>" lines.
list_all_tags() {
  local url="https://hub.docker.com/v2/repositories/${REPO}/tags/?page_size=100"
  while [[ -n "$url" && "$url" != "null" ]]; do
    local page
    page="$(curl -sf -H "Authorization: JWT ${JWT}" "$url")"
    jq -r '.results[] | "\(.name) \(.tag_last_pushed)"' <<<"$page"
    url="$(jq -r '.next' <<<"$page")"
  done
}

all_tags="$(list_all_tags)"

for service in "${SERVICES[@]}"; do
  echo "==> ${service}"
  # sha tags for this service, newest first.
  mapfile -t old_tags < <(
    grep -E "^${service}-sha-" <<<"$all_tags" \
      | sort -k2 -r \
      | awk '{print $1}' \
      | tail -n "+$((KEEP + 1))"
  )

  if [[ "${#old_tags[@]}" -eq 0 ]]; then
    echo "    nothing to prune"
    continue
  fi

  for tag in "${old_tags[@]}"; do
    echo "    deleting ${tag}"
    curl -sf -X DELETE -H "Authorization: JWT ${JWT}" \
      "https://hub.docker.com/v2/repositories/${REPO}/tags/${tag}/" >/dev/null
  done
done

echo "done."
