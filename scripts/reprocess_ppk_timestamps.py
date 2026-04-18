#!/usr/bin/env python3
"""
Reprocess PPK solution files to fix timestamps.

The original PPK processing incorrectly concatenated GPS week and time-of-week
as timestamps. This script reads the raw .pos files and regenerates ppk_gps.json
with correct ISO timestamps.
"""

import argparse
import boto3
import json
import sys
from datetime import datetime, timezone, timedelta
from io import StringIO

DATA_BUCKET = 'sailframes-fleet-data-prod'

# GPS epoch: January 6, 1980 00:00:00 UTC
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0, tzinfo=timezone.utc)


def gps_week_to_datetime(gps_week: int, tow_seconds: float) -> datetime:
    """Convert GPS week and time-of-week to datetime."""
    delta = timedelta(weeks=gps_week, seconds=tow_seconds)
    return GPS_EPOCH + delta


def parse_ppk_solution(pos_content: str) -> dict:
    """Parse RTKLIB solution file (.pos) to JSON format."""
    positions = []
    fix_count = 0
    float_count = 0
    single_count = 0

    for line in pos_content.split('\n'):
        line = line.strip()

        # Skip header lines
        if line.startswith('%') or not line:
            continue

        parts = line.split()
        if len(parts) < 8:
            continue

        try:
            # RTKLIB .pos format (GPST time system):
            # GPSWeek TOW(sec) Lat Lon Height Q ns sdn sde sdu ...
            gps_week = int(parts[0])
            tow_seconds = float(parts[1])
            lat = float(parts[2])
            lon = float(parts[3])
            height = float(parts[4])
            quality = int(parts[5])  # 1=fix, 2=float, 5=single
            num_sats = int(parts[6])

            # Parse standard deviations if available
            sdn = float(parts[7]) if len(parts) > 7 else 0
            sde = float(parts[8]) if len(parts) > 8 else 0
            sdu = float(parts[9]) if len(parts) > 9 else 0

            # Count solution types
            if quality == 1:
                fix_count += 1
            elif quality == 2:
                float_count += 1
            else:
                single_count += 1

            # Convert GPS week/TOW to ISO timestamp
            dt = gps_week_to_datetime(gps_week, tow_seconds)
            millis = int((tow_seconds % 1) * 1000)
            timestamp = dt.strftime('%Y-%m-%dT%H:%M:%S') + f'.{millis:03d}Z'

            positions.append({
                't': timestamp,
                'lat': lat,
                'lon': lon,
                'alt': height,
                'quality': quality,
                'sats': num_sats,
                'sdn': round(sdn, 4),
                'sde': round(sde, 4),
                'sdu': round(sdu, 4),
            })

        except (ValueError, IndexError) as e:
            print(f"    Warning: Error parsing line: {line[:50]}... : {e}")

    total = len(positions)
    fix_rate = (fix_count / total * 100) if total > 0 else 0

    return {
        'positions': positions,
        'fix_rate': round(fix_rate, 1),
        'fix_count': fix_count,
        'float_count': float_count,
        'single_count': single_count,
        'total': total
    }


def list_sessions_with_ppk(s3) -> list:
    """List all sessions that have ppk_solution.pos files."""
    sessions = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix='processed/'):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('/ppk_solution.pos'):
                # Extract device/folder from key
                # processed/E1/2026-04-14-152840/ppk_solution.pos
                parts = key.split('/')
                if len(parts) >= 4:
                    device_id = parts[1]
                    folder = parts[2]
                    sessions.append(f"{device_id}/{folder}")

    return sorted(sessions)


def process_session(s3, session_path: str, dry_run: bool = False) -> bool:
    """Reprocess PPK data for a single session."""
    parts = session_path.split('/')
    device_id = parts[0]
    folder = parts[1]

    pos_key = f"processed/{device_id}/{folder}/ppk_solution.pos"
    ppk_json_key = f"processed/{device_id}/{folder}/ppk_gps.json"

    # Download .pos file
    try:
        response = s3.get_object(Bucket=DATA_BUCKET, Key=pos_key)
        pos_content = response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"  Error downloading {pos_key}: {e}")
        return False

    # Parse solution
    ppk_data = parse_ppk_solution(pos_content)
    positions = ppk_data['positions']

    if not positions:
        print(f"  No positions parsed from solution file")
        return False

    print(f"  Parsed {len(positions)} positions (fix: {ppk_data['fix_count']}, float: {ppk_data['float_count']}, single: {ppk_data['single_count']})")
    print(f"  Time range: {positions[0]['t']} to {positions[-1]['t']}")

    if dry_run:
        print(f"  [DRY RUN] Would upload to {ppk_json_key}")
        return True

    # Upload updated ppk_gps.json
    s3.put_object(
        Bucket=DATA_BUCKET,
        Key=ppk_json_key,
        Body=json.dumps(positions, indent=2),
        ContentType='application/json'
    )
    print(f"  Uploaded: {ppk_json_key}")

    return True


def main():
    parser = argparse.ArgumentParser(description='Reprocess PPK timestamps')
    parser.add_argument('--session', help='Process single session (e.g., E1/2026-04-14-152840)')
    parser.add_argument('--profile', default='sailframes', help='AWS profile name')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be done')
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile)
    s3 = session.client('s3')

    if args.session:
        print(f"Processing session: {args.session}")
        success = process_session(s3, args.session, args.dry_run)
        sys.exit(0 if success else 1)
    else:
        print("Finding sessions with PPK data...")
        sessions = list_sessions_with_ppk(s3)
        print(f"Found {len(sessions)} sessions with PPK data")

        success = 0
        failed = 0

        for i, session_path in enumerate(sessions, 1):
            print(f"\n[{i}/{len(sessions)}] {session_path}")
            if process_session(s3, session_path, args.dry_run):
                success += 1
            else:
                failed += 1

        print(f"\n{'='*50}")
        print(f"Done! Success: {success}, Failed: {failed}")


if __name__ == '__main__':
    main()
