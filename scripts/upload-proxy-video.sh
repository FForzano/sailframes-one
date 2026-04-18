#!/bin/bash
# upload-proxy-video.sh - Upload merged proxy video and link to E1 session
# Usage: ./upload-proxy-video.sh <video_file> <session>
# Example: ./upload-proxy-video.sh gopro_proxy_20260409_154023.mp4 E1/2026-04-09-154138
#
# Uploads a merged/rotated proxy video and updates the session manifest.

set -e

AWS_PROFILE="${AWS_PROFILE:-sailframes}"
S3_BUCKET="sailframes-fleet-data-prod"

if [[ $# -lt 2 || "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: $0 <video_file> <session> [gps_time]"
    echo ""
    echo "Arguments:"
    echo "  video_file: Merged proxy video file (from prep-gopro-proxy.sh)"
    echo "  session: Session path (e.g., E1/2026-04-09-154138)"
    echo "  gps_time: Optional GPS start time (e.g., '2026:04:09 15:40:23.930')"
    echo "            (Required for merged videos since GPMF metadata is lost)"
    echo ""
    echo "Example:"
    echo "  $0 gopro_proxy_20260409_154023.mp4 E1/2026-04-09-154138"
    echo "  $0 gopro_proxy_20260409_154023.mp4 E1/2026-04-09-154138 '2026:04:09 15:40:23.930'"
    exit 0
fi

VIDEO_FILE="$1"
SESSION="$2"
PASSED_GPS_TIME="${3:-}"

if [[ ! -f "$VIDEO_FILE" ]]; then
    echo "Error: Video file not found: $VIDEO_FILE"
    exit 1
fi

# Parse session path
DEVICE_ID=$(echo "$SESSION" | cut -d'/' -f1)
SESSION_FOLDER=$(echo "$SESSION" | cut -d'/' -f2)

if [[ -z "$DEVICE_ID" || -z "$SESSION_FOLDER" ]]; then
    echo "Error: Invalid session format. Use: DEVICE/YYYY-MM-DD-SESSION"
    echo "Example: E1/2026-04-09-154138"
    exit 1
fi

# Check for required tools
if ! command -v ffprobe &> /dev/null; then
    echo "Error: ffprobe is required but not installed."
    echo "Install with: brew install ffmpeg"
    exit 1
fi

if ! command -v exiftool &> /dev/null; then
    echo "Error: exiftool is required but not installed."
    echo "Install with: brew install exiftool"
    exit 1
fi

echo "Upload Configuration:"
echo "  Video: $VIDEO_FILE"
echo "  Session: $SESSION"
echo "  Bucket: $S3_BUCKET"
echo ""

# Extract video metadata
echo "Extracting video metadata..."

# Get duration
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null)
DURATION_SEC=$(printf "%.1f" "$DURATION")
DURATION_MIN=$(echo "$DURATION / 60" | bc)

# Get resolution
RESOLUTION=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null)
RESOLUTION_LABEL="${RESOLUTION}p"

# Use passed GPS time, or try to extract from video, or prompt
if [[ -n "$PASSED_GPS_TIME" ]]; then
    GPS_TIME="$PASSED_GPS_TIME"
    echo "  Using provided GPS time: $GPS_TIME"
else
    # Try to get GPS start time from video metadata
    GPS_TIME=$(exiftool -api largefilesupport=1 -ee -GPSDateTime -s3 "$VIDEO_FILE" 2>/dev/null | head -1)
fi

if [[ -n "$GPS_TIME" ]]; then
    # Convert "2026:04:09 15:40:23.930" to ISO format
    START_TIME=$(echo "$GPS_TIME" | sed 's/\([0-9]\{4\}\):\([0-9]\{2\}\):\([0-9]\{2\}\) /\1-\2-\3T/' | sed 's/$/.000Z/' | sed 's/\.\([0-9]\{3\}\)\.000Z/.\1Z/')
    echo "  GPS start time: $START_TIME"
else
    # Prompt for manual time entry
    echo "  Warning: No GPS time found in video"
    read -p "  Enter start time (ISO format, e.g., 2026-04-09T15:40:23Z): " START_TIME
fi

# Calculate end time
if [[ -n "$START_TIME" && -n "$DURATION" ]]; then
    # Use Python for date math
    END_TIME=$(python3 -c "
from datetime import datetime, timedelta
start = datetime.fromisoformat('$START_TIME'.replace('Z', '+00:00'))
end = start + timedelta(seconds=$DURATION)
print(end.strftime('%Y-%m-%dT%H:%M:%S.') + f'{end.microsecond // 1000:03d}Z')
")
fi

echo "  Duration: ${DURATION_MIN} minutes (${DURATION_SEC}s)"
echo "  Resolution: $RESOLUTION_LABEL"
if [[ -n "$END_TIME" ]]; then
    echo "  End time: $END_TIME"
fi
echo ""

# Upload file
FILENAME=$(basename "$VIDEO_FILE")
S3_KEY="raw/gopro/proxy/${SESSION_FOLDER}/${FILENAME}"
S3_PATH="s3://${S3_BUCKET}/${S3_KEY}"

echo "Uploading to S3..."
FILE_SIZE=$(du -h "$VIDEO_FILE" | cut -f1)
echo "  Size: $FILE_SIZE"

# Build metadata JSON
METADATA_JSON="{\"duration-seconds\":\"$DURATION_SEC\""
if [[ -n "$START_TIME" ]]; then
    METADATA_JSON="$METADATA_JSON,\"gps-start-time\":\"$START_TIME\""
fi
METADATA_JSON="$METADATA_JSON}"

aws s3 cp "$VIDEO_FILE" "$S3_PATH" \
    --profile "$AWS_PROFILE" \
    --storage-class STANDARD_IA \
    --metadata "$METADATA_JSON"

echo "  Uploaded: $S3_PATH"
echo ""

# Update session manifest
echo "Updating session manifest..."

MANIFEST_KEY="processed/${DEVICE_ID}/${SESSION_FOLDER}/manifest.json"
MANIFEST_TMP=$(mktemp)

# Download current manifest
if ! aws s3 cp "s3://${S3_BUCKET}/${MANIFEST_KEY}" "$MANIFEST_TMP" --profile "$AWS_PROFILE" 2>/dev/null; then
    echo "Error: Could not download manifest from $MANIFEST_KEY"
    echo "Make sure the session exists."
    rm -f "$MANIFEST_TMP"
    exit 1
fi

# Update manifest with video_proxy field using Python
python3 << EOF
import json
from datetime import datetime, timezone

with open('$MANIFEST_TMP', 'r') as f:
    manifest = json.load(f)

manifest['video_proxy'] = {
    's3_key': '$S3_KEY',
    'filename': '$FILENAME',
    'start_time': '$START_TIME' if '$START_TIME' else None,
    'end_time': '$END_TIME' if '$END_TIME' else None,
    'duration_sec': $DURATION_SEC,
    'resolution': '$RESOLUTION_LABEL',
    'is_proxy': True
}

manifest['has_video'] = True
manifest['updated_at'] = datetime.now(timezone.utc).isoformat()

# Remove old chapter videos if present (proxy replaces them)
if 'videos' in manifest:
    del manifest['videos']

with open('$MANIFEST_TMP', 'w') as f:
    json.dump(manifest, f, indent=2)
EOF

# Upload updated manifest
aws s3 cp "$MANIFEST_TMP" "s3://${S3_BUCKET}/${MANIFEST_KEY}" \
    --profile "$AWS_PROFILE" \
    --content-type "application/json"

rm -f "$MANIFEST_TMP"

echo "  Updated: $MANIFEST_KEY"
echo ""
echo "================================"
echo "Done!"
echo ""
echo "View session at:"
echo "  https://sailframes.com/dashboard/?session=${SESSION}"
