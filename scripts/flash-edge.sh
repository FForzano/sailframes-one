#!/usr/bin/env bash
# Download the latest CI-built edge firmware (unified E + B) from GitHub Actions and flash it
# to a connected ESP32 over USB.
#
# Usage:
#   scripts/flash-edge.sh                  # auto-detect port, app-only flash
#   scripts/flash-edge.sh --port /dev/cu.usbserial-XXXX
#   scripts/flash-edge.sh --full           # flash bootloader + partitions + app
#   scripts/flash-edge.sh --fleet          # prompt to swap devices and reflash
#   scripts/flash-edge.sh --no-flash       # download + verify only
#   scripts/flash-edge.sh --run-id 12345   # use a specific workflow run
#
# Dependencies: gh, esptool, shasum, jq

set -euo pipefail

WORKFLOW="firmware-edge.yml"
DOWNLOAD_DIR="${TMPDIR:-/tmp}/edge-fw"
BAUD="${ESPTOOL_BAUD:-921600}"

PORT=""
FULL_FLASH=false
NO_FLASH=false
SKIP_CONFIRM=false
FLEET_MODE=false
RUN_ID_OVERRIDE=""

usage() {
  # Print the leading comment block (lines after shebang, up to first blank line)
  awk 'NR==1{next} /^$/{exit} /^#/{sub(/^# ?/,""); print}' "$0"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)      PORT="$2"; shift 2 ;;
    --full)      FULL_FLASH=true; shift ;;
    --no-flash)  NO_FLASH=true; shift ;;
    --yes|-y)    SKIP_CONFIRM=true; shift ;;
    --fleet)     FLEET_MODE=true; shift ;;
    --run-id)    RUN_ID_OVERRIDE="$2"; shift 2 ;;
    -h|--help)   usage 0 ;;
    *)           echo "Unknown option: $1" >&2; usage 1 ;;
  esac
done

# ---- Dependency check ----
for cmd in gh esptool shasum jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: missing dependency '$cmd'" >&2
    case "$cmd" in
      gh)      echo "       Install: brew install gh && gh auth login" >&2 ;;
      esptool) echo "       Install: pip install esptool  (or: brew install esptool)" >&2 ;;
      jq)      echo "       Install: brew install jq" >&2 ;;
    esac
    exit 1
  fi
done

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi

# ---- Find the run to use ----
if [[ -n "$RUN_ID_OVERRIDE" ]]; then
  RUN_ID="$RUN_ID_OVERRIDE"
  echo "==> Using run $RUN_ID (override)"
else
  echo "==> Finding latest successful build of $WORKFLOW on main..."
  RUN_JSON=$(gh run list \
    --workflow "$WORKFLOW" --branch main --status success --limit 1 \
    --json databaseId,headSha,displayTitle,createdAt)
  RUN_ID=$(echo "$RUN_JSON" | jq -r '.[0].databaseId // empty')
  if [[ -z "$RUN_ID" ]]; then
    echo "ERROR: no successful runs found on main. Has the workflow run yet?" >&2
    exit 1
  fi
  SHORT_SHA=$(echo "$RUN_JSON" | jq -r '.[0].headSha[0:7]')
  TITLE=$(echo "$RUN_JSON" | jq -r '.[0].displayTitle')
  CREATED=$(echo "$RUN_JSON" | jq -r '.[0].createdAt')
  echo "    Run:    $RUN_ID"
  echo "    Commit: $SHORT_SHA"
  echo "    Title:  $TITLE"
  echo "    Built:  $CREATED"
fi

# ---- Resolve artifact name (workflow appends full SHA) ----
ARTIFACT_NAME=$(gh api "repos/{owner}/{repo}/actions/runs/$RUN_ID/artifacts" \
  --jq '.artifacts[] | select(.name | startswith("edge-firmware-")) | .name' | head -1)
if [[ -z "$ARTIFACT_NAME" ]]; then
  echo "ERROR: no edge-firmware-* artifact on run $RUN_ID" >&2
  exit 1
fi

# ---- Download ----
TARGET="$DOWNLOAD_DIR/$ARTIFACT_NAME"
if [[ -d "$TARGET" && -n "$(ls -A "$TARGET" 2>/dev/null)" ]]; then
  echo "==> Using cached artifact at $TARGET"
else
  echo "==> Downloading artifact $ARTIFACT_NAME..."
  rm -rf "$TARGET"
  mkdir -p "$TARGET"
  gh run download "$RUN_ID" --name "$ARTIFACT_NAME" -D "$TARGET" >/dev/null
fi

# ---- Locate binaries ----
APP_BIN=$(find "$TARGET" -maxdepth 1 -name 'sailframes_edge_*.bin' \
  ! -name '*.bootloader.bin' ! -name '*.partitions.bin' \
  ! -name '*.sha256' | head -1)
if [[ -z "$APP_BIN" || ! -f "$APP_BIN" ]]; then
  echo "ERROR: app binary not found in $TARGET" >&2
  ls -la "$TARGET" >&2
  exit 1
fi
SHA_FILE="${APP_BIN}.sha256"
VERSION=$(basename "$APP_BIN" | sed -E 's/^sailframes_edge_(.+)\.bin$/\1/')
BOOT_BIN="$TARGET/sailframes_edge_${VERSION}.bootloader.bin"
PART_BIN="$TARGET/sailframes_edge_${VERSION}.partitions.bin"

echo "    Version: $VERSION"
echo "    App:     $(basename "$APP_BIN") ($(wc -c < "$APP_BIN" | tr -d ' ') bytes)"

# ---- Verify SHA256 ----
if [[ -f "$SHA_FILE" ]]; then
  echo "==> Verifying SHA256..."
  ( cd "$TARGET" && shasum -a 256 -c "$(basename "$SHA_FILE")" )
fi

if $NO_FLASH; then
  echo "==> --no-flash given. Binary at:"
  echo "    $APP_BIN"
  exit 0
fi

if $FULL_FLASH; then
  if [[ ! -f "$BOOT_BIN" || ! -f "$PART_BIN" ]]; then
    echo "ERROR: --full requested but bootloader/partitions missing in $TARGET" >&2
    exit 1
  fi
fi

# ---- Detect port (called per device for fleet mode) ----
detect_port() {
  local p
  for p in /dev/cu.usbserial-* /dev/cu.SLAB_USBtoUART* /dev/cu.usbmodem* \
           /dev/ttyUSB* /dev/ttyACM*; do
    if [[ -e "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

flash_one() {
  local port="$1"
  echo
  echo "==> Flashing $port"
  if $FULL_FLASH; then
    echo "    Mode: FULL (bootloader 0x1000 + partitions 0x8000 + app 0x10000)"
    esptool --chip esp32 --port "$port" --baud "$BAUD" \
      write-flash \
        0x1000  "$BOOT_BIN" \
        0x8000  "$PART_BIN" \
        0x10000 "$APP_BIN"
  else
    # Always wipe otadata before an app-only flash. Background:
    # the firmware uses the min_spiffs partition layout (ota_0 at
    # 0x10000, ota_1 at 0x1F0000, otadata at 0xe000). When the
    # auto-OTA pull runs, it writes the new build to the OTHER
    # slot and updates otadata to point there. A subsequent
    # serial flash to 0x10000 lands the bytes correctly but the
    # bootloader still reads otadata, sees "boot ota_1", and
    # boots the OLD firmware sitting in ota_1. Clearing otadata
    # forces a fall-back to ota_0 — exactly where we just wrote.
    # Two consecutive serial flashes have always bit this without
    # the erase, hence "always do it" instead of guessing.
    echo "    Mode: app only (0x10000) + otadata erase (0xe000 / 0x2000)"
    esptool --chip esp32 --port "$port" --baud "$BAUD" \
      erase-region 0xe000 0x2000
    esptool --chip esp32 --port "$port" --baud "$BAUD" \
      write-flash 0x10000 "$APP_BIN"
  fi
  echo "    OK — flashed $VERSION to $port"
}

flash_with_prompt() {
  local port
  if [[ -n "$PORT" ]]; then
    port="$PORT"
  else
    port=$(detect_port || true)
  fi

  if [[ -z "$port" || ! -e "$port" ]]; then
    echo "ERROR: no serial port found. Plug in the ESP32 or pass --port." >&2
    return 1
  fi

  if ! $SKIP_CONFIRM; then
    echo
    echo "About to flash:"
    echo "  Version: $VERSION"
    echo "  Port:    $port"
    read -r -p "Proceed? [Y/n] " ans
    # Empty answer (just Enter) = yes. Only "n"/"N" cancels.
    [[ -z "$ans" || "$ans" =~ ^[yY] ]] || { echo "Skipped."; return 0; }
  fi
  flash_one "$port"
}

# ---- Flash ----
if $FLEET_MODE; then
  device_num=1
  while true; do
    echo
    echo "############################################################"
    echo "# Device $device_num — plug in the next device over USB and press Enter"
    echo "# (or type 'q' then Enter to stop)"
    echo "############################################################"
    read -r line
    [[ "$line" == "q" ]] && break

    PORT=""  # force redetect each iteration
    flash_with_prompt || true
    device_num=$((device_num + 1))

    echo
    echo "Disconnect this device. Press Enter to flash the next, or 'q' to quit."
    read -r line
    [[ "$line" == "q" ]] && break
  done
  echo
  echo "==> Fleet mode done. Flashed $((device_num - 1)) device(s)."
else
  flash_with_prompt
  echo
  echo "==> Done. Open serial monitor with one of:"
  PORT_FOR_MON="${PORT:-$(detect_port || echo '<port>')}"
  echo "    screen $PORT_FOR_MON 115200      # Ctrl-A K to quit"
  echo "    arduino-cli monitor -p $PORT_FOR_MON -c baudrate=115200"
fi
