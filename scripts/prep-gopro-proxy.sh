#!/bin/bash
# prep-gopro-proxy.sh - Merge and rotate GoPro LRV proxy videos
# Usage: ./prep-gopro-proxy.sh [input_dir] [output_file]
#
# Merges all LRV chapters into a single file and rotates 180°.
# Uses ffmpeg concat demuxer (no re-encoding for merge, only rotation).

set -e

GOPRO_SD_PATH="/Volumes/Untitled/DCIM/100GOPRO"
INPUT_DIR="${1:-$GOPRO_SD_PATH}"
OUTPUT_FILE="${2:-}"

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: $0 [input_dir] [output_file]"
    echo "  input_dir: Directory containing LRV files (default: GoPro SD card)"
    echo "  output_file: Output filename (default: auto-generated from GPS time)"
    echo ""
    echo "Merges all LRV proxy videos and rotates 180° for upside-down mounting."
    exit 0
fi

if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is required but not installed."
    echo "Install with: brew install ffmpeg"
    exit 1
fi

if ! command -v exiftool &> /dev/null; then
    echo "Error: exiftool is required but not installed."
    echo "Install with: brew install exiftool"
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Directory does not exist: $INPUT_DIR"
    exit 1
fi

# Find LRV files and sort by chapter order
shopt -s nullglob nocaseglob
LRV_FILES=("$INPUT_DIR"/*.LRV)

if [[ ${#LRV_FILES[@]} -eq 0 ]]; then
    echo "No LRV files found in $INPUT_DIR"
    exit 1
fi

# Sort files: GOPR first, then GP01, GP02, etc.
IFS=$'\n' LRV_FILES=($(sort -t'/' -k2 <<<"${LRV_FILES[*]}")); unset IFS

echo "Found ${#LRV_FILES[@]} LRV files:"
for f in "${LRV_FILES[@]}"; do
    echo "  $(basename "$f")"
done
echo ""

# Extract GPS start time from first file for naming
FIRST_FILE="${LRV_FILES[0]}"
GPS_TIME=$(exiftool -api largefilesupport=1 -ee -GPSDateTime -s3 "$FIRST_FILE" 2>/dev/null | head -1)

if [[ -z "$GPS_TIME" ]]; then
    echo "Warning: Could not extract GPS time, using current date"
    DATE_STR=$(date +%Y%m%d_%H%M%S)
else
    # Convert "2026:04:09 15:40:23.930" to "20260409_154023"
    DATE_STR=$(echo "$GPS_TIME" | sed 's/[: ]//g' | cut -c1-15 | sed 's/\([0-9]\{8\}\)\([0-9]\{6\}\).*/\1_\2/')
    echo "GPS start time: $GPS_TIME"
fi

# Generate output filename if not specified
if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="gopro_proxy_${DATE_STR}.mp4"
fi

echo "Output file: $OUTPUT_FILE"
echo ""

# Create concat list file
CONCAT_LIST=$(mktemp)
for f in "${LRV_FILES[@]}"; do
    echo "file '$f'" >> "$CONCAT_LIST"
done

echo "Merging and rotating 180°..."
echo ""

# Merge with concat demuxer and rotate 180° using transpose
# -vf "transpose=1,transpose=1" = rotate 180° (two 90° rotations)
# Or use -vf "hflip,vflip" which is equivalent and faster
# Using -c:a copy to avoid re-encoding audio
# Using fast-start for web playback (moov atom at start)
ffmpeg -f concat -safe 0 -i "$CONCAT_LIST" \
    -vf "hflip,vflip" \
    -c:v libx264 -preset fast -crf 23 \
    -c:a copy \
    -movflags +faststart \
    -y "$OUTPUT_FILE"

rm "$CONCAT_LIST"

# Get output file info
OUTPUT_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
OUTPUT_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_FILE" 2>/dev/null)
OUTPUT_DURATION_MIN=$(echo "$OUTPUT_DURATION / 60" | bc)

echo ""
echo "================================"
echo "Done!"
echo "  Output: $OUTPUT_FILE"
echo "  Size: $OUTPUT_SIZE"
echo "  Duration: ${OUTPUT_DURATION_MIN} minutes"
echo ""
echo "To upload:"
echo "  ./scripts/upload-gopro-s3.sh"
