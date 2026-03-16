#!/usr/bin/env python3
"""
SailFrames Monitor Service
Monitors system health: CPU temp, battery level, disk usage, sensor status.
Provides a local web dashboard on port 8080.
Triggers clean shutdown on low battery.
"""

import os
import sys
import csv
import time
import signal
import logging
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import psutil
from flask import Flask, jsonify, render_template_string
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MONITOR] %(levelname)s %(message)s'
)
logger = logging.getLogger('sailframes.monitor')

running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def load_config():
    config_paths = [
        '/etc/sailframes/sailframes.yaml',
        os.path.join(os.path.dirname(__file__), '..', 'config', 'sailframes.yaml')
    ]
    for path in config_paths:
        if os.path.exists(path):
            with open(path) as f:
                return yaml.safe_load(f)
    logger.error("No config file found")
    sys.exit(1)


def get_cpu_temp():
    """Read Pi CPU temperature."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000, 1)
    except Exception:
        return None


def get_battery_info():
    """
    Read battery status from UPS HAT via I2C.
    This is HAT-specific - adjust for your UPS HAT model.
    Returns dict with voltage, percent, charging status.
    """
    try:
        import smbus2
        bus = smbus2.SMBus(1)

        # UeeKKoo UPS HAT (D) typically uses INA219 or MAX17048 fuel gauge
        # Common I2C address: 0x36 (MAX17048) or 0x40 (INA219)
        # Adjust these registers for your specific UPS HAT

        # Try MAX17048 fuel gauge (common on many UPS HATs)
        try:
            # Voltage register (0x02) - 16-bit, 78.125µV/cell resolution
            data = bus.read_word_data(0x36, 0x02)
            # Byte swap (little endian to big endian)
            voltage_raw = ((data & 0xFF) << 8) | ((data >> 8) & 0xFF)
            voltage = voltage_raw * 78.125 / 1_000_000  # Convert to volts

            # SOC register (0x04) - state of charge in %
            data = bus.read_word_data(0x36, 0x04)
            soc_raw = ((data & 0xFF) << 8) | ((data >> 8) & 0xFF)
            percent = soc_raw / 256.0

            bus.close()
            return {
                'voltage': round(voltage, 3),
                'percent': round(min(percent, 100), 1),
                'charging': voltage > 4.1,  # Rough heuristic
            }
        except Exception:
            pass

        bus.close()
    except Exception:
        pass

    return {'voltage': None, 'percent': None, 'charging': None}


def get_disk_usage(mount_point):
    """Get disk usage for data storage."""
    try:
        usage = psutil.disk_usage(mount_point)
        return {
            'total_gb': round(usage.total / (1024**3), 1),
            'used_gb': round(usage.used / (1024**3), 1),
            'free_gb': round(usage.free / (1024**3), 1),
            'percent': usage.percent,
        }
    except Exception:
        return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}


def check_service_status(service_name):
    """Check if a systemd service is running."""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == 'active'
    except Exception:
        return False


# ── System state (shared between monitor thread and web server) ──
system_state = {
    'device_id': '',
    'uptime_sec': 0,
    'cpu_temp_c': None,
    'cpu_percent': 0,
    'ram_percent': 0,
    'battery': {},
    'disk': {},
    'services': {},
    'last_update': '',
}


def monitor_loop(config):
    """Background thread that collects system stats."""
    global system_state, running

    monitor_config = config['monitor']
    interval = monitor_config['stats_interval_sec']
    shutdown_percent = monitor_config['battery_shutdown_percent']
    data_mount = config['storage']['ssd_mount']

    system_state['device_id'] = config['device']['id']

    while running:
        system_state['cpu_temp_c'] = get_cpu_temp()
        system_state['cpu_percent'] = psutil.cpu_percent(interval=1)
        system_state['ram_percent'] = psutil.virtual_memory().percent
        system_state['battery'] = get_battery_info()
        system_state['disk'] = get_disk_usage(data_mount)
        system_state['uptime_sec'] = int(time.monotonic())
        system_state['last_update'] = datetime.now(timezone.utc).isoformat()

        # Check service status
        system_state['services'] = {
            'gps': check_service_status('sailframes-gps'),
            'imu': check_service_status('sailframes-imu'),
            'pressure': check_service_status('sailframes-pressure'),
            'wind': check_service_status('sailframes-wind'),
            'camera': check_service_status('sailframes-camera'),
        }

        # Low battery shutdown
        battery_pct = system_state['battery'].get('percent')
        if battery_pct is not None and battery_pct < shutdown_percent:
            logger.warning(f"Battery at {battery_pct}%! Initiating clean shutdown.")
            subprocess.run(['sudo', 'shutdown', '-h', 'now'])
            running = False
            return

        # Log summary periodically
        logger.info(
            f"CPU={system_state['cpu_temp_c']}°C "
            f"RAM={system_state['ram_percent']}% "
            f"Disk={system_state['disk'].get('free_gb', '?')}GB free "
            f"Batt={battery_pct or '?'}%"
        )

        time.sleep(interval)


# ── Web Dashboard ──
app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SailFrames - {{ state.device_id }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="5">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; background: #0a1628; color: #e0e8f0; padding: 16px; }
        h1 { color: #4fc3f7; margin-bottom: 16px; font-size: 24px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .card { background: #1a2a40; border-radius: 8px; padding: 14px; }
        .card h2 { font-size: 13px; color: #78909c; text-transform: uppercase; margin-bottom: 8px; }
        .value { font-size: 28px; font-weight: 700; color: #fff; }
        .unit { font-size: 14px; color: #78909c; }
        .status { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
        .status.on { background: #4caf50; }
        .status.off { background: #f44336; }
        .services { margin-top: 12px; }
        .svc-row { padding: 6px 0; font-size: 14px; border-bottom: 1px solid #233; }
        .updated { font-size: 11px; color: #546e7a; margin-top: 12px; text-align: center; }
    </style>
</head>
<body>
    <h1>⛵ SailFrames {{ state.device_id }}</h1>
    <div class="grid">
        <div class="card">
            <h2>CPU Temp</h2>
            <div class="value">{{ state.cpu_temp_c or '—' }}<span class="unit">°C</span></div>
        </div>
        <div class="card">
            <h2>Battery</h2>
            <div class="value">{{ state.battery.percent or '—' }}<span class="unit">%</span></div>
        </div>
        <div class="card">
            <h2>Disk Free</h2>
            <div class="value">{{ state.disk.free_gb or '—' }}<span class="unit">GB</span></div>
        </div>
        <div class="card">
            <h2>RAM</h2>
            <div class="value">{{ state.ram_percent or '—' }}<span class="unit">%</span></div>
        </div>
    </div>
    <div class="card services" style="margin-top: 12px;">
        <h2>Sensor Services</h2>
        {% for name, active in state.services.items() %}
        <div class="svc-row">
            <span class="status {{ 'on' if active else 'off' }}"></span>
            {{ name }}
        </div>
        {% endfor %}
    </div>
    <div class="updated">Updated {{ state.last_update }}</div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML, state=system_state)

@app.route('/api/status')
def api_status():
    return jsonify(system_state)


def run(config):
    monitor_config = config['monitor']
    port = monitor_config['web_port']

    # Start monitor thread
    monitor_thread = threading.Thread(target=monitor_loop, args=(config,), daemon=True)
    monitor_thread.start()
    logger.info("Monitor thread started")

    # Start web dashboard
    logger.info(f"Dashboard at http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    config = load_config()
    if not config['monitor']['enabled']:
        logger.info("Monitor disabled in config, exiting")
        sys.exit(0)
    run(config)
