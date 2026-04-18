#!/usr/bin/env python3
"""
Restore deleted sessions by reprocessing raw data files.

This script:
1. Lists all raw CSV files in S3
2. Invokes the process_upload Lambda for each file to recreate processed JSON
3. Recreates manifest.json files

Usage:
    python scripts/restore_sessions.py
    python scripts/restore_sessions.py --dry-run
"""

import argparse
import boto3
import json
import time

DATA_BUCKET = 'sailframes-fleet-data-prod'
PROCESS_LAMBDA = 'sailframes-process-upload-prod'


def list_raw_files(s3, prefix='raw/'):
    """List all raw CSV/RTCM3 files."""
    files = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            # Include CSV and RTCM3 files
            if key.endswith('.csv') or key.endswith('.rtcm3'):
                files.append(key)

    return sorted(files)


def invoke_process_lambda(lambda_client, bucket: str, key: str, dry_run: bool = False) -> bool:
    """Invoke the process_upload Lambda for a single file."""

    # Build S3 event payload
    event = {
        'Records': [{
            's3': {
                'bucket': {'name': bucket},
                'object': {'key': key}
            }
        }]
    }

    if dry_run:
        print(f"  [DRY RUN] Would invoke Lambda for: {key}")
        return True

    try:
        response = lambda_client.invoke(
            FunctionName=PROCESS_LAMBDA,
            InvocationType='RequestResponse',  # Sync to see errors
            Payload=json.dumps(event)
        )

        payload = json.loads(response['Payload'].read())
        status_code = payload.get('statusCode', 0)

        if status_code == 200:
            return True
        else:
            print(f"  Warning: Lambda returned {status_code}: {payload.get('body', '')}")
            return status_code == 207  # Partial success

    except Exception as e:
        print(f"  Error invoking Lambda: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Restore sessions from raw data')
    parser.add_argument('--profile', default='sailframes', help='AWS profile name')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be done')
    parser.add_argument('--device', help='Only process specific device (e.g., E1, sailframes-01)')
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name='us-east-1')
    s3 = session.client('s3')
    lambda_client = session.client('lambda')

    # List all raw files
    prefix = f"raw/{args.device}/" if args.device else "raw/"
    print(f"Listing raw files in s3://{DATA_BUCKET}/{prefix}...")
    files = list_raw_files(s3, prefix)
    print(f"Found {len(files)} files to process")

    if not files:
        print("No files found!")
        return

    # Group files by session for progress reporting
    sessions = {}
    for f in files:
        parts = f.split('/')
        if len(parts) >= 3:
            session_key = f"{parts[1]}/{parts[2]}"  # device/date
            sessions.setdefault(session_key, []).append(f)

    print(f"Files belong to {len(sessions)} sessions:")
    for session_key in sorted(sessions.keys()):
        print(f"  {session_key}: {len(sessions[session_key])} files")

    if not args.dry_run:
        confirm = input("\nProceed with processing? (y/n): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return

    # Process each file
    success = 0
    failed = 0

    for i, key in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {key}")

        if invoke_process_lambda(lambda_client, DATA_BUCKET, key, args.dry_run):
            success += 1
        else:
            failed += 1

        # Small delay to avoid throttling
        if not args.dry_run:
            time.sleep(0.1)

    print(f"\n{'='*50}")
    print(f"Done! Success: {success}, Failed: {failed}")

    if not args.dry_run:
        print("\nVerifying restored sessions...")
        # List manifest files
        paginator = s3.get_paginator('list_objects_v2')
        manifests = []
        for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix='processed/'):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('manifest.json'):
                    manifests.append(obj['Key'])

        print(f"Found {len(manifests)} session manifests:")
        for m in sorted(manifests):
            print(f"  {m}")


if __name__ == '__main__':
    main()
