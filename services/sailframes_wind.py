#!/usr/bin/env python3
"""
SailFrames Wind Service
Connects to Calypso Mini CMI1022 ultrasonic anemometer via BLE.
Parses wind speed and direction from NMEA-like BLE characteristics.
"""

import os
import sys
import csv
import time
import signal
import struct
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from bleak import BleakClient, BleakScanner
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [WIND] %(levelname)s %(message)s'
)
logger = logging.getLogger('sailframes.wind')

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


# Calypso Mini BLE UUIDs
# These are the standard Calypso BLE service and characteristic UUIDs.
# The wind data characteristic sends binary packets with speed and direction.
CALYPSO_SERVICE_UUID = "0000a000-0000-1000-8000-00805f9b34fb"
CALYPSO_WIND_CHAR_UUID = "0000a001-0000-1000-8000-00805f9b34fb"

# Alternative: some Calypso firmware versions use these UUIDs
CALYPSO_ALT_SERVICE_UUID = "00001800-0000-1000-8000-00805f9b34fb"


def get_data_dir(config):
    base = config['storage']['data_dir']
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    data_dir = Path(base) / today / 'wind'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def create_csv_writer(data_dir):
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filepath = data_dir / f'wind_{timestamp}.csv'
    f = open(filepath, 'w', newline='')
    writer = csv.writer(f)
    writer.writerow([
        'utc_time',
        'apparent_wind_speed_knots',   # Apparent wind speed
        'apparent_wind_speed_mps',     # Apparent wind speed in m/s
        'apparent_wind_angle_deg',     # Apparent wind angle (0-360, 0=bow)
        'battery_percent',             # Sensor battery level (if available)
        'temperature_c',               # Sensor temperature (if available)
    ])
    logger.info(f"Logging to {filepath}")
    return f, writer


def parse_calypso_data(data):
    """
    Parse Calypso Mini BLE wind data packet.
    
    The Calypso BLE protocol sends wind data as binary packets.
    Format varies by firmware version. Common format:
    - Byte 0-1: Wind speed (uint16, 0.01 m/s resolution)
    - Byte 2-3: Wind direction (uint16, degrees)
    - Byte 4: Battery level (uint8, percent)
    - Byte 5: Temperature (int8, Celsius)
    
    Note: Verify against your specific Calypso firmware version.
    The open protocol documentation is available from Calypso.
    """
    if len(data) < 4:
        return None

    try:
        # Try common Calypso binary format
        wind_speed_raw = struct.unpack('<H', data[0:2])[0]
        wind_dir_raw = struct.unpack('<H', data[2:4])[0]

        wind_speed_mps = wind_speed_raw / 100.0  # Convert to m/s
        wind_speed_knots = wind_speed_mps * 1.94384  # Convert to knots
        wind_angle = wind_dir_raw  # Degrees

        result = {
            'speed_mps': round(wind_speed_mps, 2),
            'speed_knots': round(wind_speed_knots, 2),
            'angle_deg': wind_angle,
            'battery': None,
            'temperature': None,
        }

        if len(data) >= 5:
            result['battery'] = data[4]
        if len(data) >= 6:
            result['temperature'] = struct.unpack('b', bytes([data[5]]))[0]

        return result

    except Exception as e:
        logger.warning(f"Parse error: {e}, raw data: {data.hex()}")
        return None


async def scan_for_calypso(config):
    """Scan for Calypso Mini sensor by name or MAC address."""
    wind_config = config['wind']
    mac = wind_config.get('ble_mac_address', '')
    timeout = wind_config['ble_scan_timeout_sec']

    if mac:
        logger.info(f"Looking for Calypso at MAC {mac}")
        device = await BleakScanner.find_device_by_address(mac, timeout=timeout)
        if device:
            return device

    # Scan by name if MAC not set or not found
    logger.info("Scanning for Calypso devices...")
    devices = await BleakScanner.discover(timeout=timeout)
    for device in devices:
        name = device.name or ''
        if 'calypso' in name.lower() or 'ultrasonic' in name.lower():
            logger.info(f"Found Calypso: {device.name} at {device.address}")
            logger.info(f"Set ble_mac_address: \"{device.address}\" in config for faster reconnect")
            return device

    return None


async def run_async(config):
    wind_config = config['wind']
    reconnect_interval = wind_config['ble_reconnect_interval_sec']

    data_dir = get_data_dir(config)
    csv_file, writer = create_csv_writer(data_dir)
    rows_written = 0

    while running:
        # Find sensor
        device = await scan_for_calypso(config)
        if device is None:
            logger.warning("Calypso not found, retrying...")
            await asyncio.sleep(reconnect_interval)
            continue

        logger.info(f"Connecting to {device.name} ({device.address})")

        try:
            async with BleakClient(device.address, timeout=20) as client:
                logger.info("BLE connected")

                # Define notification handler
                def wind_callback(sender, data):
                    nonlocal rows_written, csv_file, writer, data_dir

                    parsed = parse_calypso_data(data)
                    if parsed is None:
                        return

                    utc_now = datetime.now(timezone.utc).isoformat()
                    writer.writerow([
                        utc_now,
                        parsed['speed_knots'],
                        parsed['speed_mps'],
                        parsed['angle_deg'],
                        parsed['battery'] or '',
                        parsed['temperature'] or '',
                    ])
                    rows_written += 1

                    if rows_written % 60 == 0:
                        csv_file.flush()
                        logger.debug(
                            f"AWS={parsed['speed_knots']:.1f}kn "
                            f"AWA={parsed['angle_deg']}° "
                            f"Batt={parsed['battery']}%"
                        )

                # Subscribe to wind data notifications
                await client.start_notify(CALYPSO_WIND_CHAR_UUID, wind_callback)
                logger.info("Subscribed to wind data notifications")

                # Stay connected until disconnected or shutdown
                while running and client.is_connected:
                    await asyncio.sleep(1)

                    # Rotate file at midnight
                    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    if data_dir.parent.name != current_date:
                        csv_file.close()
                        data_dir = get_data_dir(config)
                        csv_file, writer = create_csv_writer(data_dir)
                        rows_written = 0

        except Exception as e:
            logger.warning(f"BLE connection error: {e}")

        if running:
            logger.info(f"Reconnecting in {reconnect_interval}s...")
            await asyncio.sleep(reconnect_interval)

    csv_file.close()
    logger.info(f"Wind service stopped. {rows_written} rows written.")


def run(config):
    asyncio.run(run_async(config))


if __name__ == '__main__':
    config = load_config()
    if not config['wind']['enabled']:
        logger.info("Wind disabled in config, exiting")
        sys.exit(0)
    run(config)
