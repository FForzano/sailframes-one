"""
SailFrames API - Get Video Manifest
Returns HLS playlist URLs for session video streams.
"""

import json
import os
import boto3
import logging
import re
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
DATA_BUCKET = os.environ.get('DATA_BUCKET', 'sailframes-data-prod')
CLOUDFRONT_DOMAIN = os.environ.get('CLOUDFRONT_DOMAIN', 'sailframes.com')


def lambda_handler(event, context):
    """Return video stream information for a session."""
    try:
        path_params = event.get('pathParameters', {})
        device_id = path_params.get('device_id')
        date = path_params.get('date')

        if not device_id or not date:
            return error_response(400, 'Missing device_id or date')

        streams = get_video_streams(device_id, date)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'streams': streams})
        }
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return error_response(500, str(e))


def error_response(status: int, message: str) -> dict:
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': message})
    }


def get_video_streams(device_id: str, date: str) -> dict:
    """Get HLS stream info for all cameras."""
    streams = {}

    for camera in ['cockpit', 'sails']:
        prefix = f"hls/{device_id}/{date}/{camera}/"

        # Check for playlist
        playlist_key = f"{prefix}playlist.m3u8"
        try:
            s3.head_object(Bucket=DATA_BUCKET, Key=playlist_key)
        except s3.exceptions.ClientError:
            continue

        # List segments
        segments = []
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('.ts'):
                    # Extract timestamp from filename
                    filename = key.split('/')[-1]
                    ts_match = re.search(r'(\d{8}_\d{6})', filename)
                    if ts_match:
                        ts_str = ts_match.group(1)
                        try:
                            start_time = datetime.strptime(ts_str, '%Y%m%d_%H%M%S')
                            segments.append({
                                'start': start_time.isoformat() + 'Z',
                                'duration': 300,  # 5 minute segments
                                'key': key
                            })
                        except ValueError:
                            pass

        # Sort segments by time
        segments.sort(key=lambda s: s['start'])

        streams[camera] = {
            'playlist_url': f"https://{CLOUDFRONT_DOMAIN}/hls/{device_id}/{date}/{camera}/playlist.m3u8",
            'start_time': segments[0]['start'] if segments else None,
            'segments': [{'start': s['start'], 'duration': s['duration']} for s in segments]
        }

    return streams
