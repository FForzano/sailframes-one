#!/bin/bash
# upload-gopro.sh - One-click GoPro proxy upload with auto session matching
# Usage: ./upload-gopro.sh
#
# Merges LRV chapters, finds matching E1 session, and uploads.
# No parameters needed - reads from GoPro SD card and auto-matches session.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_PROFILE="${AWS_PROFILE:-sailframes}"
S3_BUCKET="sailframes-fleet-data-prod"
GOPRO_SD_PATH="/Volumes/Untitled/DCIM/100GOPRO"

echo "=========================================="
echo "GoPro One-Click Upload"
echo "=========================================="
echo ""

# Check for required tools
for cmd in exiftool ffmpeg ffprobe aws python3; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

# Check GoPro SD card
if [[ ! -d "$GOPRO_SD_PATH" ]]; then
    echo "Error: GoPro SD card not found at $GOPRO_SD_PATH"
    echo ""
    echo "Is the SD card mounted? Check: ls /Volumes/"
    exit 1
fi

# Find LRV files
shopt -s nullglob nocaseglob
LRV_FILES=("$GOPRO_SD_PATH"/*.LRV)

if [[ ${#LRV_FILES[@]} -eq 0 ]]; then
    echo "Error: No LRV files found on GoPro SD card"
    exit 1
fi

echo "Found ${#LRV_FILES[@]} LRV files on SD card"
echo ""

# Step 1: Merge LRV files
echo "Step 1: Merging LRV files..."
echo "----------------------------------------"

# Check if a recent proxy file already exists (within last hour)
EXISTING_PROXY=$(ls -t gopro_proxy_*.mp4 2>/dev/null | head -1)
if [[ -n "$EXISTING_PROXY" && -f "$EXISTING_PROXY" ]]; then
    # Check if file is less than 1 hour old
    FILE_AGE=$(($(date +%s) - $(stat -f%m "$EXISTING_PROXY" 2>/dev/null || stat -c%Y "$EXISTING_PROXY" 2>/dev/null)))
    if [[ $FILE_AGE -lt 3600 ]]; then
        echo "Found recent proxy file: $EXISTING_PROXY (${FILE_AGE}s old)"
        read -p "Use existing file instead of re-merging? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            PROXY_FILE="$EXISTING_PROXY"
        fi
    fi
fi

if [[ -z "$PROXY_FILE" ]]; then
    # Run prep-gopro-proxy.sh and capture output filename
    OUTPUT=$("$SCRIPT_DIR/prep-gopro-proxy.sh" 2>&1 | tee /dev/stderr)
    PROXY_FILE=$(echo "$OUTPUT" | grep -o 'gopro_proxy_[0-9_]*.mp4' | head -1)

    if [[ -z "$PROXY_FILE" || ! -f "$PROXY_FILE" ]]; then
        echo "Error: Could not find merged proxy file"
        exit 1
    fi
    echo ""
    echo "Created: $PROXY_FILE"
fi

echo ""

# Step 2: Extract GPS time and find matching session
echo "Step 2: Finding matching E1 session..."
echo "----------------------------------------"

# Extract GPS start time from ORIGINAL LRV file (merged video loses GPMF metadata)
# GPS time is UTC and accurate - don't use MP4 creation_time (has timezone issues)
FIRST_LRV="${LRV_FILES[0]}"
GPS_TIME=$(exiftool -api largefilesupport=1 -ee -GPSDateTime -s3 "$FIRST_LRV" 2>/dev/null | head -1)

if [[ -z "$GPS_TIME" ]]; then
    echo "Error: Could not extract GPS time from LRV file"
    echo "Make sure GoPro GPS was enabled during recording."
    echo ""
    echo "You can manually specify the session:"
    echo "  ./scripts/upload-proxy-video.sh <video.mp4> E1/<session>"
    exit 1
fi

echo "Video start time: $GPS_TIME"

# Get video duration
VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$PROXY_FILE" 2>/dev/null)
VIDEO_DURATION_MIN=$(echo "$VIDEO_DURATION / 60" | bc)
echo "Video duration: ${VIDEO_DURATION_MIN} minutes"

# Parse date from GPS time (format: "2026:04:09 15:40:23.930")
VIDEO_DATE=$(echo "$GPS_TIME" | sed 's/\([0-9]\{4\}\):\([0-9]\{2\}\):\([0-9]\{2\}\).*/\1-\2-\3/')
echo "Video date: $VIDEO_DATE"

# Convert to comparable timestamp (seconds since epoch)
VIDEO_TS=$(python3 -c "
from datetime import datetime
gps_time = '$GPS_TIME'
# Parse '2026:04:09 15:40:23.930' format
dt = datetime.strptime(gps_time[:19], '%Y:%m:%d %H:%M:%S')
print(int(dt.timestamp()))
")

echo "Looking for E1 sessions on $VIDEO_DATE..."

# List E1 sessions for this date
SESSIONS=$(aws s3 ls "s3://${S3_BUCKET}/processed/E1/" --profile "$AWS_PROFILE" | grep "$VIDEO_DATE" | awk '{print $2}' | tr -d '/')

if [[ -z "$SESSIONS" ]]; then
    echo "Error: No E1 sessions found for $VIDEO_DATE"
    echo ""
    echo "Available sessions:"
    aws s3 ls "s3://${S3_BUCKET}/processed/E1/" --profile "$AWS_PROFILE" | tail -10
    exit 1
fi

echo "Found sessions:"
for s in $SESSIONS; do
    echo "  $s"
done

# Find best matching session (closest start time)
BEST_SESSION=""
BEST_DIFF=999999999

for SESSION_FOLDER in $SESSIONS; do
    # Download manifest to get start/end times
    MANIFEST=$(aws s3 cp "s3://${S3_BUCKET}/processed/E1/${SESSION_FOLDER}/manifest.json" - --profile "$AWS_PROFILE" 2>/dev/null)

    if [[ -n "$MANIFEST" ]]; then
        # Extract start and end times
        SESSION_START=$(echo "$MANIFEST" | python3 -c "import sys,json; m=json.load(sys.stdin); print(m.get('start_time',''))" 2>/dev/null)
        SESSION_END=$(echo "$MANIFEST" | python3 -c "import sys,json; m=json.load(sys.stdin); print(m.get('end_time',''))" 2>/dev/null)

        if [[ -n "$SESSION_START" && -n "$SESSION_END" ]]; then
            # Check if video overlaps with session (video is 95min long typically)
            MATCH=$(python3 -c "
from datetime import datetime, timedelta

video_start = datetime.strptime('$GPS_TIME'[:19], '%Y:%m:%d %H:%M:%S')
# Video duration from proxy file (or estimate 95 min)
try:
    import subprocess
    dur = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', '$PROXY_FILE'], stderr=subprocess.DEVNULL).decode().strip()
    video_duration = timedelta(seconds=float(dur))
except:
    video_duration = timedelta(minutes=95)  # Default estimate

video_end = video_start + video_duration

session_start = datetime.fromisoformat('$SESSION_START'.replace('Z', '+00:00')).replace(tzinfo=None)
session_end = datetime.fromisoformat('$SESSION_END'.replace('Z', '+00:00')).replace(tzinfo=None)

# Check for ANY overlap between video and session (with 5min buffer)
buffer = timedelta(minutes=5)
session_start_buf = session_start - buffer
session_end_buf = session_end + buffer

# Overlap: video_start < session_end AND video_end > session_start
if video_start <= session_end_buf and video_end >= session_start_buf:
    # Calculate how close video start is to session start
    diff = abs((video_start - session_start).total_seconds())
    print(f'MATCH:{int(diff)}')
else:
    print('NO_MATCH')
" 2>/dev/null)

            if [[ "$MATCH" == MATCH:* ]]; then
                DIFF=${MATCH#MATCH:}
                echo "  $SESSION_FOLDER: MATCH (offset: ${DIFF}s)"
                echo "    Session: $SESSION_START to $SESSION_END"
                if [[ $DIFF -lt $BEST_DIFF ]]; then
                    BEST_DIFF=$DIFF
                    BEST_SESSION=$SESSION_FOLDER
                fi
            else
                echo "  $SESSION_FOLDER: no overlap"
                echo "    Session: $SESSION_START to $SESSION_END"
            fi
        fi
    fi
done

if [[ -z "$BEST_SESSION" ]]; then
    echo ""
    echo "Error: No matching session found for video time $GPS_TIME"
    echo ""
    echo "You can manually specify the session:"
    echo "  ./scripts/upload-proxy-video.sh $PROXY_FILE E1/<session>"
    exit 1
fi

echo ""
echo "Best match: E1/$BEST_SESSION"
echo ""

# Step 3: Upload and link
echo "Step 3: Uploading and linking to session..."
echo "----------------------------------------"

"$SCRIPT_DIR/upload-proxy-video.sh" "$PROXY_FILE" "E1/$BEST_SESSION" "$GPS_TIME"

# Step 4: Cleanup
echo ""
echo "Step 4: Cleanup..."
echo "----------------------------------------"
read -p "Delete local proxy file ($PROXY_FILE)? [Y/n] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    rm "$PROXY_FILE"
    echo "Deleted: $PROXY_FILE"
fi

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="
echo ""
echo "View at: https://sailframes.com/dashboard/?session=E1/$BEST_SESSION"
