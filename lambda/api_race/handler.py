"""
SailFrames API - Race and Regatta endpoints.
Handles CRUD operations for races/regattas, multi-boat data loading,
and GPX track uploads as a GPS source for boats without E1 devices.
"""

import base64
import json
import logging
import math
import os
import re
import uuid
import xml.etree.ElementTree as ET
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

            # GPX upload: POST /api/races/{race_id}/boats/{device_id}/gpx
            if race_id and '/gpx' in path and http_method == 'POST':
                device_id = path_params.get('device_id')
                if not device_id:
                    m = re.search(r'/boats/([^/]+)/gpx', path)
                    device_id = m.group(1) if m else None
                if not device_id:
                    return response(400, {'error': 'device_id required'})
                return upload_boat_gpx(race_id, device_id, event)

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
        gpx_path = boat.get('gpx_path')

        if not session_path and not gpx_path:
            boats_data[device_id] = {'error': 'No session matched', 'boat': boat}
            continue

        boat_sensors = {}
        for sensor in requested_sensors:
            # GPX upload serves as the GPS source for this boat
            if sensor == 'gps' and gpx_path:
                try:
                    data = load_json(gpx_path)
                    if isinstance(data, list):
                        filtered = [d for d in data if _in_window(d.get('t', ''), start_time, end_time)]
                        boat_sensors[sensor] = filtered
                    else:
                        boat_sensors[sensor] = []
                except Exception as e:
                    boat_sensors[sensor] = {'error': str(e)}
                continue

            if not session_path:
                boat_sensors[sensor] = []
                continue

            try:
                sensor_key = f"processed/{device_id}/{session_path}/{sensor}.json"
                data = load_json(sensor_key)
                if isinstance(data, list):
                    filtered = [d for d in data if _in_window(d.get('t', ''), start_time, end_time)]
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


def _in_window(t, start, end):
    """Check if timestamp t falls within [start, end] using normalized ISO comparison."""
    # Normalize: strip trailing Z and milliseconds for consistent comparison
    def norm(s):
        return s.replace('Z', '').split('.')[0] if s else ''
    tn, s, e = norm(t), norm(start), norm(end)
    return s <= tn <= e


# --- GPX Upload ---

def upload_boat_gpx(race_id, device_id, event):
    """Parse a GPX file upload and store it as the GPS source for a boat."""
    race_data = load_json(f'races/{race_id}/race.json')
    if not race_data:
        return response(404, {'error': f'Race not found: {race_id}'})

    boat = next((b for b in race_data.get('boats', []) if b['device_id'] == device_id), None)
    if boat is None:
        return response(404, {'error': f'Boat {device_id} not found in race {race_id}'})

    gpx_bytes = _extract_multipart_file(event)
    if not gpx_bytes:
        return response(400, {'error': 'No file received — send as multipart/form-data with field name "file"'})

    try:
        track_points = _parse_gpx(gpx_bytes)
    except Exception as e:
        logger.error(f"GPX parse error: {e}", exc_info=True)
        return response(400, {'error': f'Failed to parse GPX: {e}'})

    if not track_points:
        return response(400, {'error': 'GPX file contains no track points with timestamps'})

    gpx_key = f'races/{race_id}/gpx/{device_id}.json'
    save_json(gpx_key, track_points)

    boat['gpx_path'] = gpx_key
    boat['session_path'] = None  # GPX replaces E1 session
    race_data['updated_at'] = now_iso()
    save_json(f'races/{race_id}/race.json', race_data)

    logger.info(f"GPX uploaded for {device_id} in race {race_id}: {len(track_points)} points")

    return response(200, {
        'device_id': device_id,
        'gpx_path': gpx_key,
        'points': len(track_points),
        'start_time': track_points[0]['t'],
        'end_time': track_points[-1]['t'],
    })


def _extract_multipart_file(event):
    """Extract the raw file bytes from a multipart/form-data Lambda event."""
    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    content_type = headers.get('content-type', '')

    body_raw = event.get('body', '') or ''
    if event.get('isBase64Encoded'):
        body_bytes = base64.b64decode(body_raw)
    else:
        body_bytes = body_raw.encode('latin-1')

    # Extract boundary from Content-Type header
    boundary = None
    for part in content_type.split(';'):
        part = part.strip()
        if part.lower().startswith('boundary='):
            boundary = part[9:].strip('"\'')
            break

    if not boundary:
        # No multipart — treat the raw body as the file
        return body_bytes if body_bytes else None

    delimiter = ('--' + boundary).encode('latin-1')
    parts = body_bytes.split(delimiter)

    for part in parts[1:]:  # skip preamble
        if part in (b'--', b'--\r\n', b''):
            continue
        # Split headers from body
        sep = b'\r\n\r\n'
        if sep not in part:
            continue
        _, file_body = part.split(sep, 1)
        file_body = file_body.rstrip(b'\r\n')
        if file_body:
            return file_body

    return None


# --- GPX Parsing ---

def _parse_gpx(content: bytes) -> list:
    """Parse GPX XML into GPS track points matching processed gps.json format."""
    root = ET.fromstring(content)
    ns_match = re.match(r'\{([^}]+)\}', root.tag)
    ns = f"{{{ns_match.group(1)}}}" if ns_match else ""

    raw = []
    for seg in root.iter(f"{ns}trkseg"):
        for trkpt in seg.iter(f"{ns}trkpt"):
            lat = float(trkpt.get('lat', 0))
            lon = float(trkpt.get('lon', 0))
            time_el = trkpt.find(f"{ns}time")
            if time_el is None or not time_el.text:
                continue
            t = time_el.text.strip()

            speed_ms = None
            for el in trkpt.iter():
                local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
                if local == 'speed' and el.text:
                    try:
                        speed_ms = float(el.text)
                    except ValueError:
                        pass
                    break

            raw.append({'lat': lat, 'lon': lon, 't': t, '_speed_ms': speed_ms})

    result = []
    for i, pt in enumerate(raw):
        sog = 0.0
        cog = 0.0

        if pt['_speed_ms'] is not None:
            sog = pt['_speed_ms'] * 1.94384  # m/s → knots
        elif i > 0:
            prev = raw[i - 1]
            try:
                dt = iso_diff_seconds(pt['t'], prev['t'])
                if dt > 0:
                    dist_m = _haversine_m(prev['lat'], prev['lon'], pt['lat'], pt['lon'])
                    sog = (dist_m / dt) * 1.94384
            except Exception:
                pass

        if i > 0:
            prev = raw[i - 1]
            cog = _bearing(prev['lat'], prev['lon'], pt['lat'], pt['lon'])
        elif i < len(raw) - 1:
            nxt = raw[i + 1]
            cog = _bearing(pt['lat'], pt['lon'], nxt['lat'], nxt['lon'])

        result.append({
            't': pt['t'],
            'lat': pt['lat'],
            'lon': pt['lon'],
            'sog': round(sog, 2),
            'cog': round(cog, 1),
        })

    return result


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


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
