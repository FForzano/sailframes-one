"""
SailFrames API - Race and Regatta endpoints.
Handles CRUD operations for races/regattas and multi-boat data loading.
"""

import json
import os
import uuid
import logging
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
DATA_BUCKET = os.environ.get('DATA_BUCKET', 'sailframes-fleet-data-prod')

# S3 paths for race data
RACES_INDEX_KEY = "races/races.json"
REGATTAS_INDEX_KEY = "regattas/regattas.json"

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}


def lambda_handler(event, context):
    """Handle race API requests."""
    http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'GET')
    path = event.get('rawPath', '') or event.get('path', '')
    path_params = event.get('pathParameters', {}) or {}

    logger.info(f"Request: {http_method} {path} params={path_params}")

    # Handle CORS preflight
    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': '{}'}

    try:
        # Route to appropriate handler
        # Regattas
        if '/api/regattas' in path:
            if http_method == 'GET' and not path_params.get('regatta_id'):
                return list_regattas()
            elif http_method == 'GET':
                return get_regatta(path_params['regatta_id'])
            elif http_method == 'POST':
                return create_regatta(json.loads(event.get('body', '{}')))
            elif http_method == 'PATCH':
                return update_regatta(path_params['regatta_id'], json.loads(event.get('body', '{}')))
            elif http_method == 'DELETE':
                return delete_regatta(path_params['regatta_id'])

        # Races
        elif '/api/races' in path:
            race_id = path_params.get('race_id')

            # Match sessions endpoint
            if race_id and '/match-sessions' in path and http_method == 'POST':
                return match_sessions(race_id)

            # Race data endpoint
            if race_id and '/data' in path and http_method == 'GET':
                qs = event.get('queryStringParameters', {}) or {}
                sensors = qs.get('sensors', 'gps,imu,wind')
                return get_race_data(race_id, sensors)

            # CRUD operations
            if http_method == 'GET' and not race_id:
                qs = event.get('queryStringParameters', {}) or {}
                return list_races(qs.get('regatta_id'), qs.get('date'))
            elif http_method == 'GET':
                return get_race(race_id)
            elif http_method == 'POST':
                return create_race(json.loads(event.get('body', '{}')))
            elif http_method == 'PATCH':
                return update_race(race_id, json.loads(event.get('body', '{}')))
            elif http_method == 'DELETE':
                return delete_race(race_id)

        return response(404, {'error': 'Not found'})

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return response(500, {'error': str(e)})


def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body)
    }


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def load_json(key):
    try:
        resp = s3.get_object(Bucket=DATA_BUCKET, Key=key)
        return json.loads(resp['Body'].read())
    except s3.exceptions.NoSuchKey:
        return {}
    except Exception:
        return {}


def save_json(key, data):
    s3.put_object(
        Bucket=DATA_BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def delete_json(key):
    try:
        s3.delete_object(Bucket=DATA_BUCKET, Key=key)
    except Exception:
        pass


# --- Regattas ---

def list_regattas():
    data = load_json(REGATTAS_INDEX_KEY)
    return response(200, {'regattas': data.get('regattas', [])})


def get_regatta(regatta_id):
    data = load_json(REGATTAS_INDEX_KEY)
    for regatta in data.get('regattas', []):
        if regatta['regatta_id'] == regatta_id:
            races_data = load_json(RACES_INDEX_KEY)
            races = [r for r in races_data.get('races', []) if r.get('regatta_id') == regatta_id]
            return response(200, {**regatta, 'races': races})
    return response(404, {'error': f'Regatta not found: {regatta_id}'})


def create_regatta(body):
    regatta_id = str(uuid.uuid4())[:8]
    now = now_iso()

    new_regatta = {
        'regatta_id': regatta_id,
        'name': body.get('name', ''),
        'venue': body.get('venue', ''),
        'boat_class': body.get('boat_class', ''),
        'start_date': body.get('start_date', ''),
        'end_date': body.get('end_date', ''),
        'race_ids': [],
        'created_at': now,
        'updated_at': now,
    }

    data = load_json(REGATTAS_INDEX_KEY)
    if not data:
        data = {'regattas': []}
    data['regattas'].append(new_regatta)
    save_json(REGATTAS_INDEX_KEY, data)

    return response(201, new_regatta)


def update_regatta(regatta_id, body):
    data = load_json(REGATTAS_INDEX_KEY)
    for i, regatta in enumerate(data.get('regattas', [])):
        if regatta['regatta_id'] == regatta_id:
            for key in ['name', 'venue', 'start_date', 'end_date']:
                if key in body and body[key] is not None:
                    regatta[key] = body[key]
            regatta['updated_at'] = now_iso()
            data['regattas'][i] = regatta
            save_json(REGATTAS_INDEX_KEY, data)
            return response(200, regatta)
    return response(404, {'error': f'Regatta not found: {regatta_id}'})


def delete_regatta(regatta_id):
    data = load_json(REGATTAS_INDEX_KEY)
    original_len = len(data.get('regattas', []))
    data['regattas'] = [r for r in data.get('regattas', []) if r['regatta_id'] != regatta_id]
    if len(data['regattas']) == original_len:
        return response(404, {'error': f'Regatta not found: {regatta_id}'})
    save_json(REGATTAS_INDEX_KEY, data)
    return response(200, {'deleted': regatta_id})


# --- Races ---

def list_races(regatta_id=None, date=None):
    data = load_json(RACES_INDEX_KEY)
    races = data.get('races', [])

    if regatta_id:
        races = [r for r in races if r.get('regatta_id') == regatta_id]
    if date:
        races = [r for r in races if r.get('date') == date]

    races = sorted(races, key=lambda r: (r.get('date', ''), r.get('start_time', '')))
    return response(200, {'races': races})


def get_race(race_id):
    race_data = load_json(f'races/{race_id}/race.json')
    if not race_data:
        return response(404, {'error': f'Race not found: {race_id}'})
    return response(200, race_data)


def create_race(body):
    race_id = str(uuid.uuid4())[:8]
    now = now_iso()

    boats = body.get('boats', [])
    if isinstance(boats, list):
        boats = [b if isinstance(b, dict) else {} for b in boats]

    new_race = {
        'race_id': race_id,
        'name': body.get('name', ''),
        'date': body.get('date', ''),
        'start_time': body.get('start_time', ''),
        'end_time': body.get('end_time', ''),
        'regatta_id': body.get('regatta_id'),
        'boats': boats,
        'start_line': body.get('start_line'),
        'finish_line': body.get('finish_line'),
        'finish_order': body.get('finish_order', []),
        'results': None,
        'created_at': now,
        'updated_at': now,
    }

    # Save race definition
    save_json(f'races/{race_id}/race.json', new_race)

    # Update races index
    data = load_json(RACES_INDEX_KEY)
    if not data:
        data = {'races': []}
    data['races'].append({
        'race_id': race_id,
        'name': new_race['name'],
        'date': new_race['date'],
        'start_time': new_race['start_time'],
        'end_time': new_race['end_time'],
        'regatta_id': new_race['regatta_id'],
        'boat_count': len(boats),
    })
    save_json(RACES_INDEX_KEY, data)

    # Update regatta if linked
    if new_race['regatta_id']:
        regattas_data = load_json(REGATTAS_INDEX_KEY)
        for regatta in regattas_data.get('regattas', []):
            if regatta['regatta_id'] == new_race['regatta_id']:
                if race_id not in regatta.get('race_ids', []):
                    regatta.setdefault('race_ids', []).append(race_id)
                    regatta['updated_at'] = now
                break
        save_json(REGATTAS_INDEX_KEY, regattas_data)

    return response(201, new_race)


def update_race(race_id, body):
    race_data = load_json(f'races/{race_id}/race.json')
    if not race_data:
        return response(404, {'error': f'Race not found: {race_id}'})

    for key in ['name', 'start_time', 'end_time', 'boats', 'start_line', 'finish_line', 'finish_order']:
        if key in body and body[key] is not None:
            race_data[key] = body[key]

    race_data['updated_at'] = now_iso()
    save_json(f'races/{race_id}/race.json', race_data)

    # Update index
    data = load_json(RACES_INDEX_KEY)
    for i, r in enumerate(data.get('races', [])):
        if r['race_id'] == race_id:
            data['races'][i]['name'] = race_data['name']
            data['races'][i]['start_time'] = race_data['start_time']
            data['races'][i]['end_time'] = race_data['end_time']
            data['races'][i]['boat_count'] = len(race_data.get('boats', []))
            break
    save_json(RACES_INDEX_KEY, data)

    return response(200, race_data)


def delete_race(race_id):
    race_data = load_json(f'races/{race_id}/race.json')
    if not race_data:
        return response(404, {'error': f'Race not found: {race_id}'})

    delete_json(f'races/{race_id}/race.json')
    delete_json(f'races/{race_id}/results.json')

    # Update index
    data = load_json(RACES_INDEX_KEY)
    data['races'] = [r for r in data.get('races', []) if r['race_id'] != race_id]
    save_json(RACES_INDEX_KEY, data)

    # Update regatta if linked
    if race_data.get('regatta_id'):
        regattas_data = load_json(REGATTAS_INDEX_KEY)
        for regatta in regattas_data.get('regattas', []):
            if regatta['regatta_id'] == race_data['regatta_id']:
                regatta['race_ids'] = [rid for rid in regatta.get('race_ids', []) if rid != race_id]
                regatta['updated_at'] = now_iso()
                break
        save_json(REGATTAS_INDEX_KEY, regattas_data)

    return response(200, {'deleted': race_id})


# --- Race Data ---

def get_race_data(race_id, sensors_str):
    race_data = load_json(f'races/{race_id}/race.json')
    if not race_data:
        return response(404, {'error': f'Race not found: {race_id}'})

    start_time = race_data['start_time']
    end_time = race_data['end_time']
    requested_sensors = [s.strip() for s in sensors_str.split(',')]

    boats_data = {}

    for boat in race_data.get('boats', []):
        device_id = boat['device_id']
        session_path = boat.get('session_path')

        if not session_path:
            boats_data[device_id] = {'error': 'No session matched', 'boat': boat}
            continue

        boat_sensors = {}
        for sensor in requested_sensors:
            try:
                sensor_key = f"processed/{device_id}/{session_path}/{sensor}.json"
                data = load_json(sensor_key)
                if isinstance(data, list):
                    filtered = [d for d in data if start_time <= d.get('t', '') <= end_time]
                    boat_sensors[sensor] = filtered
                else:
                    boat_sensors[sensor] = data
            except Exception as e:
                boat_sensors[sensor] = {'error': str(e)}

        boats_data[device_id] = {
            'boat': boat,
            'sensors': boat_sensors,
        }

    return response(200, {
        'race': {
            'race_id': race_id,
            'name': race_data['name'],
            'date': race_data['date'],
            'start_time': start_time,
            'end_time': end_time,
        },
        'boats': boats_data,
        'time_bounds': {'start': start_time, 'end': end_time},
    })


# --- Session Matching ---

def match_sessions(race_id):
    race_data = load_json(f'races/{race_id}/race.json')
    if not race_data:
        return response(404, {'error': f'Race not found: {race_id}'})

    race_start = race_data['start_time']
    race_end = race_data['end_time']
    race_date = race_data['date']

    matched = []
    for boat in race_data.get('boats', []):
        device_id = boat['device_id']

        try:
            sessions = find_device_sessions(device_id, race_date)
        except Exception:
            sessions = []

        best_session = None
        best_overlap = 0

        for session in sessions:
            session_start = session.get('start_time', '')
            session_end = session.get('end_time', '')

            overlap_start = max(race_start, session_start)
            overlap_end = min(race_end, session_end)

            if overlap_start < overlap_end:
                overlap_duration = iso_diff_seconds(overlap_end, overlap_start)
                if overlap_duration > best_overlap:
                    best_overlap = overlap_duration
                    best_session = session

        if best_session:
            boat['session_path'] = best_session['session_path']
            matched.append({
                'device_id': device_id,
                'session_path': best_session['session_path'],
                'overlap_sec': best_overlap,
            })
        else:
            matched.append({
                'device_id': device_id,
                'session_path': None,
                'error': 'No overlapping session found',
            })

    race_data['updated_at'] = now_iso()
    save_json(f'races/{race_id}/race.json', race_data)

    return response(200, {'race_id': race_id, 'matched': matched})


def find_device_sessions(device_id, date):
    sessions = []
    prefix = f"processed/{device_id}/{date}"

    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix=prefix):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('/manifest.json'):
                    try:
                        resp = s3.get_object(Bucket=DATA_BUCKET, Key=obj['Key'])
                        manifest = json.loads(resp['Body'].read())
                        parts = obj['Key'].split('/')
                        session_folder = parts[-2]
                        sessions.append({
                            'session_path': f"{date}/{session_folder}",
                            'start_time': manifest.get('start_time', ''),
                            'end_time': manifest.get('end_time', ''),
                        })
                    except Exception:
                        pass
    except Exception:
        pass

    return sessions


def iso_diff_seconds(end, start):
    try:
        fmt = "%Y-%m-%dT%H:%M:%S"
        start_clean = start.replace('Z', '').split('.')[0]
        end_clean = end.replace('Z', '').split('.')[0]
        start_dt = datetime.strptime(start_clean, fmt)
        end_dt = datetime.strptime(end_clean, fmt)
        return (end_dt - start_dt).total_seconds()
    except Exception:
        return 0
