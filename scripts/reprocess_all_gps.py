#!/usr/bin/env python3
"""
Reprocess all GPS sessions to add sat, hdop, and fix fields.

Usage:
    python scripts/reprocess_all_gps.py
    python scripts/reprocess_all_gps.py --dry-run
    python scripts/reprocess_all_gps.py --session E1/2026-04-07-175325
"""

import argparse
import boto3
import csv
import json
import sys
from io import StringIO
from datetime import datetime
from collections import defaultdict

DATA_BUCKET = 'sailframes-fleet-data-prod'


def extract_gps_date_from_csv(csv_content: str) -> str:
    """Extract the actual UTC date from GPS CSV data."""
    reader = csv.DictReader(StringIO(csv_content))
    for row in reader:
        gps_date = row.get('gps_date', '')
        if gps_date and len(gps_date) == 6:
            try:
                day = int(gps_date[:2])
                month = int(gps_date[2:4])
                year = 2000 + int(gps_date[4:6])
                if 1 <= day <= 31 and 1 <= month <= 12:
                    return f"{year}-{month:02d}-{day:02d}"
            except ValueError:
                pass
    return None


def process_gps_full(csv_content: str, date: str) -> tuple:
    """Process GPS CSV to both 1Hz and 10Hz resolution.

    Returns (data_1hz, data_10hz, actual_date)
    """
    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)
    if not rows:
        return [], [], date

    first_row = rows[0]
    is_e1_format = 'utc' in first_row and 'lat' in first_row

    # Extract actual GPS date
    actual_date = date
    if is_e1_format:
        gps_date = extract_gps_date_from_csv(csv_content)
        if gps_date:
            actual_date = gps_date

    all_records_10hz = []
    by_second = defaultdict(list)

    for row in rows:
        if is_e1_format:
            utc_raw = row.get('utc', '')
            if not utc_raw:
                continue
            try:
                utc_float = float(utc_raw)
                hours = int(utc_float // 10000)
                minutes = int((utc_float % 10000) // 100)
                seconds = int(utc_float % 100)
                millis = int((utc_float % 1) * 1000)
                full_ts = f"{actual_date}T{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}Z"
                second = f"{actual_date}T{hours:02d}:{minutes:02d}:{seconds:02d}"
            except ValueError:
                continue

            fix = int(row.get('fix', 0) or 0)
            lat = abs(float(row.get('lat', 0) or 0))
            lon = abs(float(row.get('lon', 0) or 0))
            hdop = float(row.get('hdop', 99) or 99)

            if fix >= 1 and lat > 1.0 and lon > 1.0 and hdop < 10:
                record = {
                    't': full_ts,
                    'lat': float(row.get('lat', 0) or 0),
                    'lon': float(row.get('lon', 0) or 0),
                    'speed_kn': round(float(row.get('sog', 0) or 0), 2),
                    'course': round(float(row.get('cog', 0) or 0), 1),
                    'fix': fix,
                    'sats': int(row.get('sat', 0) or 0),
                    'hdop': round(hdop, 1)
                }
                all_records_10hz.append(record)
                by_second[second].append(row)
        else:
            # S1 format
            ts = row.get('utc_time', '')
            if not ts:
                continue

            try:
                second = ts[:19]
                if len(ts) > 19 and '.' in ts:
                    millis = ts[20:23] if len(ts) > 22 else ts[20:]
                    full_ts = ts[:19] + '.' + millis + 'Z'
                else:
                    full_ts = second + 'Z'
            except:
                continue

            record = {
                't': full_ts,
                'lat': float(row.get('latitude', 0) or 0),
                'lon': float(row.get('longitude', 0) or 0),
                'speed_kn': round(float(row.get('speed_knots', 0) or 0), 2),
                'course': round(float(row.get('course_deg', 0) or 0), 1),
                'fix': int(row.get('fix_quality', 0) or 0),
                'sats': int(row.get('satellites', 0) or 0),
                'hdop': round(float(row.get('hdop', 99) or 99), 1)
            }
            all_records_10hz.append(record)
            by_second[second].append(row)

    # Sort 10Hz data
    all_records_10hz.sort(key=lambda x: x['t'])

    # Take sample with max speed per second for 1Hz
    result_1hz = []
    for second, samples in sorted(by_second.items()):
        if is_e1_format:
            valid_samples = []
            for s in samples:
                fix = int(s.get('fix', 0) or 0)
                lat = abs(float(s.get('lat', 0) or 0))
                lon = abs(float(s.get('lon', 0) or 0))
                hdop = float(s.get('hdop', 99) or 99)
                if fix >= 1 and lat > 1.0 and lon > 1.0 and hdop < 10:
                    valid_samples.append(s)
            if not valid_samples:
                continue
            best = max(valid_samples, key=lambda r: float(r.get('sog', 0) or 0))
            result_1hz.append({
                't': second + 'Z',
                'lat': float(best.get('lat', 0) or 0),
                'lon': float(best.get('lon', 0) or 0),
                'speed_kn': round(float(best.get('sog', 0) or 0), 2),
                'course': round(float(best.get('cog', 0) or 0), 1),
                'fix': int(best.get('fix', 0) or 0),
                'sats': int(best.get('sat', 0) or 0),
                'hdop': round(float(best.get('hdop', 99) or 99), 1)
            })
        else:
            best = max(samples, key=lambda r: float(r.get('speed_knots', 0) or 0))
            result_1hz.append({
                't': second + 'Z',
                'lat': float(best.get('latitude', 0) or 0),
                'lon': float(best.get('longitude', 0) or 0),
                'speed_kn': round(float(best.get('speed_knots', 0) or 0), 2),
                'course': round(float(best.get('course_deg', 0) or 0), 1),
                'fix': int(best.get('fix_quality', 0) or 0),
                'sats': int(best.get('satellites', 0) or 0),
                'hdop': round(float(best.get('hdop', 99) or 99), 1)
            })

    return result_1hz, all_records_10hz, actual_date


def list_all_sessions(s3):
    """List all processed sessions."""
    sessions = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix='processed/', Delimiter='/'):
        for prefix in page.get('CommonPrefixes', []):
            device_prefix = prefix['Prefix']  # e.g., 'processed/E1/'
            device_id = device_prefix.split('/')[1]

            # List sessions for this device
            for page2 in paginator.paginate(Bucket=DATA_BUCKET, Prefix=device_prefix, Delimiter='/'):
                for session_prefix in page2.get('CommonPrefixes', []):
                    folder = session_prefix['Prefix'].split('/')[2]
                    sessions.append(f"{device_id}/{folder}")

    return sorted(sessions)


def find_raw_nav_files(s3, device_id: str, date: str, session_ids: list) -> list:
    """Find raw nav CSV files for the given session IDs."""
    files = []
    prefix = f"raw/{device_id}/{date}/"

    try:
        response = s3.list_objects_v2(Bucket=DATA_BUCKET, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj['Key']
            filename = key.split('/')[-1]

            if '_nav.csv' in filename:
                # Check if this file belongs to any of our session IDs
                for session_id in session_ids:
                    if session_id in filename:
                        files.append(key)
                        break
                else:
                    # Also check for datetime-based filenames (E1_YYYYMMDD_HHMMSS_nav.csv)
                    # where session_id might just be the HHMMSS part
                    for session_id in session_ids:
                        if len(session_id) == 6 and session_id.isdigit():
                            if f"_{session_id}_" in filename:
                                files.append(key)
                                break
    except Exception as e:
        print(f"  Warning: Error listing raw files: {e}")

    return files


def process_session(s3, session_path: str, dry_run: bool = False) -> bool:
    """Process a single session. Returns True if successful."""
    parts = session_path.split('/')
    if len(parts) != 2:
        print(f"  Invalid session path format")
        return False

    device_id = parts[0]
    folder = parts[1]
    date = folder[:10]

    # Load manifest
    manifest_key = f"processed/{device_id}/{folder}/manifest.json"
    try:
        response = s3.get_object(Bucket=DATA_BUCKET, Key=manifest_key)
        manifest = json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"  Error loading manifest: {e}")
        return False

    # Get session IDs (including merged)
    session_ids = manifest.get('merged_sessions', [])
    if manifest.get('session_id') and manifest['session_id'] not in session_ids:
        session_ids.append(manifest['session_id'])

    if not session_ids:
        # Try extracting from folder name
        if len(folder) > 10:
            session_ids = [folder[11:]]  # Skip "YYYY-MM-DD-"
        else:
            session_ids = [folder]

    # Find raw nav files
    raw_files = find_raw_nav_files(s3, device_id, date, session_ids)

    if not raw_files:
        print(f"  No raw nav files found for session IDs: {session_ids}")
        return False

    print(f"  Found {len(raw_files)} raw nav file(s)")

    # Process all files
    all_1hz = []
    all_10hz = []

    for raw_key in raw_files:
        print(f"    Processing: {raw_key.split('/')[-1]}")
        try:
            response = s3.get_object(Bucket=DATA_BUCKET, Key=raw_key)
            csv_content = response['Body'].read().decode('utf-8')

            data_1hz, data_10hz, actual_date = process_gps_full(csv_content, date)
            print(f"      -> {len(data_1hz)} 1Hz, {len(data_10hz)} 10Hz records")

            all_1hz.extend(data_1hz)
            all_10hz.extend(data_10hz)
        except Exception as e:
            print(f"      Error: {e}")

    if not all_1hz:
        print(f"  No valid GPS data extracted")
        return False

    # Deduplicate and sort
    def dedupe_sort(records):
        seen = set()
        unique = []
        for r in records:
            t = r['t']
            if t not in seen:
                seen.add(t)
                unique.append(r)
        unique.sort(key=lambda x: x['t'])
        return unique

    all_1hz = dedupe_sort(all_1hz)
    all_10hz = dedupe_sort(all_10hz)

    print(f"  Total: {len(all_1hz)} 1Hz, {len(all_10hz)} 10Hz unique records")

    if dry_run:
        print(f"  [DRY RUN] Would upload gps.json and gps_10hz.json")
        if all_1hz:
            print(f"  Sample 1Hz: {json.dumps(all_1hz[0])}")
        return True

    # Upload gps.json (1Hz)
    gps_key = f"processed/{device_id}/{folder}/gps.json"
    s3.put_object(
        Bucket=DATA_BUCKET,
        Key=gps_key,
        Body=json.dumps(all_1hz),
        ContentType='application/json'
    )
    print(f"  Uploaded: gps.json ({len(all_1hz)} records)")

    # Upload gps_10hz.json
    gps_10hz_key = f"processed/{device_id}/{folder}/gps_10hz.json"
    s3.put_object(
        Bucket=DATA_BUCKET,
        Key=gps_10hz_key,
        Body=json.dumps(all_10hz),
        ContentType='application/json'
    )
    print(f"  Uploaded: gps_10hz.json ({len(all_10hz)} records)")

    return True


def main():
    parser = argparse.ArgumentParser(description='Reprocess GPS data to add sat, hdop, fix fields')
    parser.add_argument('--session', help='Process single session (e.g., E1/2026-04-07-175325)')
    parser.add_argument('--profile', default='sailframes', help='AWS profile name')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be done')
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile)
    s3 = session.client('s3')

    if args.session:
        # Single session
        print(f"Processing session: {args.session}")
        success = process_session(s3, args.session, args.dry_run)
        sys.exit(0 if success else 1)
    else:
        # All sessions
        print("Listing all sessions...")
        sessions = list_all_sessions(s3)
        print(f"Found {len(sessions)} sessions")

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
