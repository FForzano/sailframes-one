#!/usr/bin/env python3
"""
Backfill GPX track JSON files in S3 to use the dashboard's expected field
names: rename `sog` -> `speed_kn` and `cog` -> `course`.

Background: _parse_gpx() originally emitted `sog`/`cog`, but the rest of
the pipeline (dashboard map marker, TWA/VMG/polar/layline calcs, leg
ranking) reads `speed_kn`/`course`. The parser was fixed on 2026-05-05;
this one-shot brings already-uploaded GPX files into the new shape so we
don't have to re-upload them per race.

Files touched: s3://sailframes-fleet-data-prod/races/*/gpx/*.json
"""
import argparse
import json
import sys

import boto3

BUCKET = 'sailframes-fleet-data-prod'
REGION = 'us-east-2'
PREFIX = 'races/'


def rewrite_points(points):
    changed = 0
    for p in points:
        if 'sog' in p and 'speed_kn' not in p:
            p['speed_kn'] = p.pop('sog')
            changed += 1
        if 'cog' in p and 'course' not in p:
            p['course'] = p.pop('cog')
    return changed


def process_key(s3, key, dry_run):
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    data = json.loads(obj['Body'].read())
    if not isinstance(data, list):
        return False, 'not a list'
    if not data:
        return False, 'empty'
    sample = data[0]
    if 'speed_kn' in sample and 'course' in sample and 'sog' not in sample:
        return False, 'already migrated'
    n = rewrite_points(data)
    if n == 0:
        return False, 'no sog/cog fields found'
    if not dry_run:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(data).encode('utf-8'),
            ContentType='application/json',
        )
    return True, f'rewrote {n} points'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--profile', default='sailframes')
    parser.add_argument('--race', help='Limit to a single race_id')
    args = parser.parse_args()

    sess = boto3.Session(profile_name=args.profile, region_name=REGION)
    s3 = sess.client('s3')

    prefix = f'{PREFIX}{args.race}/gpx/' if args.race else PREFIX
    paginator = s3.get_paginator('list_objects_v2')
    keys = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            k = obj['Key']
            if '/gpx/' in k and k.endswith('.json'):
                keys.append(k)

    print(f'Mode: {"DRY RUN" if args.dry_run else "LIVE"}')
    print(f'Found {len(keys)} GPX files')
    if not keys:
        return 0

    rewrote = skipped = errored = 0
    for k in keys:
        try:
            changed, note = process_key(s3, k, args.dry_run)
        except Exception as e:
            errored += 1
            print(f'  ERROR  {k}: {e}')
            continue
        if changed:
            rewrote += 1
            print(f'  REWROTE {k}  ({note})')
        else:
            skipped += 1
            print(f'  skip   {k}  ({note})')

    print(f'\nDone. rewrote={rewrote} skipped={skipped} errored={errored}')
    return 0 if errored == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
