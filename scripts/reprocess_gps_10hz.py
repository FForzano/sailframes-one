#!/usr/bin/env python3
"""
Reprocess raw GPS CSV files to generate 10Hz JSON data.

Usage:
    python scripts/reprocess_gps_10hz.py E1/2026-04-07-175325

This script:
1. Reads the manifest to find merged session IDs
2. Downloads raw GPS CSV files for all merged sessions
3. Processes them at full 10Hz resolution
4. Uploads gps_10hz.json to the processed folder
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
    """Extract the actual UTC date from GPS CSV data.

    E1 CSV has 'gps_date' column in DDMMYY format.
    Returns: Date string in YYYY-MM-DD format, or None
    """
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


def process_gps_10hz(csv_content: str, date: str) -> list:
    """Process GPS CSV to full 10Hz resolution.

    Returns list of GPS records with millisecond timestamps.
    """
    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)
    if not rows:
        return []

    # Detect format
    first_row = rows[0]
    is_e1_format = 'utc' in first_row and 'lat' in first_row

    # Extract actual GPS date
    actual_date = date
    if is_e1_format:
        gps_date = extract_gps_date_from_csv(csv_content)
        if gps_date:
            actual_date = gps_date
            print(f"  Using GPS date: {actual_date}")

    records = []
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
            except ValueError:
                continue

            # Filter invalid records
            fix = int(row.get('fix', 0) or 0)
            lat = abs(float(row.get('lat', 0) or 0))
            lon = abs(float(row.get('lon', 0) or 0))
            hdop = float(row.get('hdop', 99) or 99)

            if fix >= 1 and lat > 1.0 and lon > 1.0 and hdop < 10:
                records.append({
                    't': full_ts,
                    'lat': float(row.get('lat', 0) or 0),
                    'lon': float(row.get('lon', 0) or 0),
                    'speed_kn': round(float(row.get('sog', 0) or 0), 2),
                    'course': round(float(row.get('cog', 0) or 0), 1),
                    'fix': fix,
                    'sats': int(row.get('sat', 0) or 0)
                })
        else:
            # S1 format
            ts = row.get('utc_time', '')
            if not ts:
                continue

            if len(ts) > 19 and '.' in ts:
                millis = ts[20:23] if len(ts) > 22 else ts[20:]
                full_ts = ts[:19] + '.' + millis + 'Z'
            else:
                full_ts = ts[:19] + 'Z'

            records.append({
                't': full_ts,
                'lat': float(row.get('latitude', 0) or 0),
                'lon': float(row.get('longitude', 0) or 0),
                'speed_kn': round(float(row.get('speed_knots', 0) or 0), 2),
                'course': round(float(row.get('course_deg', 0) or 0), 1),
                'fix': int(row.get('fix_quality', 0) or 0),
                'sats': int(row.get('satellites', 0) or 0)
            })

    return records


def main():
    parser = argparse.ArgumentParser(description='Reprocess GPS data to 10Hz')
    parser.add_argument('session', help='Session path (e.g., E1/2026-04-07-175325)')
    parser.add_argument('--profile', default='sailframes', help='AWS profile name')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be done without uploading')
    args = parser.parse_args()

    # Parse session path
    parts = args.session.split('/')
    if len(parts) != 2:
        print(f"Error: Invalid session path format. Expected 'DEVICE/DATE-SESSION'")
        sys.exit(1)

    device_id = parts[0]
    folder = parts[1]

    # Extract date from folder (first 10 chars: YYYY-MM-DD)
    date = folder[:10]

    print(f"Processing session: {device_id}/{folder}")
    print(f"Date: {date}")

    # Setup S3 client
    session = boto3.Session(profile_name=args.profile)
    s3 = session.client('s3')

    # Load manifest
    manifest_key = f"processed/{device_id}/{folder}/manifest.json"
    print(f"Loading manifest: {manifest_key}")

    try:
        response = s3.get_object(Bucket=DATA_BUCKET, Key=manifest_key)
        manifest = json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"Error loading manifest: {e}")
        sys.exit(1)

    # Get session IDs to process (including merged sessions)
    session_ids = manifest.get('merged_sessions', [])
    if manifest.get('session_id') and manifest['session_id'] not in session_ids:
        session_ids.append(manifest['session_id'])

    print(f"Session IDs to process: {session_ids}")

    # Find and download raw GPS files
    all_records = []

    for session_id in session_ids:
        # List raw files for this date
        prefix = f"raw/{device_id}/{date}/"
        response = s3.list_objects_v2(Bucket=DATA_BUCKET, Prefix=prefix)

        for obj in response.get('Contents', []):
            key = obj['Key']
            filename = key.split('/')[-1]

            # Match nav files containing this session_id
            if '_nav.csv' in filename and session_id in filename:
                print(f"Processing: {key}")

                # Download CSV
                response = s3.get_object(Bucket=DATA_BUCKET, Key=key)
                csv_content = response['Body'].read().decode('utf-8')

                # Process to 10Hz
                records = process_gps_10hz(csv_content, date)
                print(f"  Extracted {len(records)} valid 10Hz records")
                all_records.extend(records)

    if not all_records:
        print("No GPS records found!")
        sys.exit(1)

    # Deduplicate and sort by timestamp
    seen = set()
    unique_records = []
    for record in all_records:
        t = record['t']
        if t not in seen:
            seen.add(t)
            unique_records.append(record)

    unique_records.sort(key=lambda x: x['t'])

    print(f"\nTotal unique 10Hz records: {len(unique_records)}")
    print(f"Time range: {unique_records[0]['t']} to {unique_records[-1]['t']}")

    # Upload
    output_key = f"processed/{device_id}/{folder}/gps_10hz.json"

    if args.dry_run:
        print(f"\n[DRY RUN] Would upload to: {output_key}")
        print(f"Sample record: {json.dumps(unique_records[0], indent=2)}")
    else:
        print(f"\nUploading to: {output_key}")
        s3.put_object(
            Bucket=DATA_BUCKET,
            Key=output_key,
            Body=json.dumps(unique_records),
            ContentType='application/json'
        )
        print(f"Done! Uploaded {len(unique_records)} records ({len(json.dumps(unique_records))} bytes)")


if __name__ == '__main__':
    main()
