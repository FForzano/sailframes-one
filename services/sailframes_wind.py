#!/usr/bin/env python3
"""
SailFrames Wind Service
Connects to Calypso Mini CMI1022 ultrasonic anemometer via BLE.
Parses wind speed and direction from NMEA-like BLE characteristics.
"""

import os
import sys
import csv
import json
import time
import signal
import struct
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from bleak import BleakClient, BleakScanner
import yaml

# Shared status file for dashboard to read current wind data
WIND_STATUS_FILE = Path('/tmp/sailframes-wind-status.json')

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


# Calypso Ultrasonic Portable Mini BLE UUIDs
# Uses standard Bluetooth Environmental Sensing Service (0x181a)
WIND_SPEED_CHAR_UUID = "00002a72-0000-1000-8000-00805f9b34fb"      # Apparent Wind Speed
WIND_DIRECTION_CHAR_UUID = "00002a73-0000-1000-8000-00805f9b34fb"  # Apparent Wind Direction
BATTERY_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"         # Battery Level

# Nordic UART Service (alternative data stream - NMEA format)
UART_RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


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


def update_wind_status(parsed, device_name=None, device_address=None, connected=True):
    """Write current wind data to status file for dashboard."""
    try:
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'connected': connected,
            'device_name': device_name,
            'device_address': device_address,
            'speed_knots': parsed.get('speed_knots') if parsed else None,
            'speed_mps': parsed.get('speed_mps') if parsed else None,
            'angle_deg': parsed.get('angle_deg') if parsed else None,
            'battery': parsed.get('battery') if parsed else None,
            'temperature': parsed.get('temperature') if parsed else None,
        }
        with open(WIND_STATUS_FILE, 'w') as f:
            json.dump(status, f)
    except Exception as e:
        logger.warning(f"Failed to update status file: {e}")


def clear_wind_status():
    """Clear status file when disconnected."""
    try:
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'connected': False,
            'device_name': None,
            'device_address': None,
        }
        with open(WIND_STATUS_FILE, 'w') as f:
            json.dump(status, f)
    except Exception:
        pass


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

    # Current wind state (updated by separate notifications)
    wind_state = {
        'speed_mps': 0.0,
        'speed_knots': 0.0,
        'angle_deg': 0,
        'battery': None,
        'temperature': None,
    }
    last_write = 0

    while running:
        # Find sensor
        device = await scan_for_calypso(config)
        if device is None:
            logger.warning("Calypso not found, retrying...")
            await asyncio.sleep(reconnect_interval)
            continue

        logger.info(f"Connecting to {device.name} ({device.address})")

        try:
            async with BleakClient(device.address, timeout=30) as client:
                logger.info("BLE connected")
                device_name = device.name
                device_address = device.address

                # Wind speed notification handler (uint16, 0.01 m/s resolution)
                def speed_callback(sender, data):
                    nonlocal last_write, rows_written, csv_file, writer, data_dir
                    if len(data) >= 2:
                        raw = struct.unpack('<H', data[0:2])[0]
                        wind_state['speed_mps'] = raw / 100.0
                        wind_state['speed_knots'] = wind_state['speed_mps'] * 1.94384
                        write_wind_data()

                # Wind direction notification handler (uint16, 0.01 degree resolution)
                def direction_callback(sender, data):
                    if len(data) >= 2:
                        raw = struct.unpack('<H', data[0:2])[0]
                        wind_state['angle_deg'] = int(raw / 100.0)

                # Battery notification handler (uint8, percent)
                def battery_callback(sender, data):
                    if len(data) >= 1:
                        wind_state['battery'] = data[0]

                def write_wind_data():
                    nonlocal last_write, rows_written, csv_file, writer, data_dir
                    now = time.time()
                    # Write at most once per second
                    if now - last_write < 1.0:
                        return
                    last_write = now

                    # Update status file for dashboard
                    update_wind_status(wind_state, device_name, device_address, connected=True)

                    utc_now = datetime.now(timezone.utc).isoformat()
                    writer.writerow([
                        utc_now,
                        round(wind_state['speed_knots'], 2),
                        round(wind_state['speed_mps'], 2),
                        wind_state['angle_deg'],
                        wind_state['battery'] or '',
                        wind_state['temperature'] or '',
                    ])
                    rows_written += 1

                    if rows_written % 60 == 0:
                        csv_file.flush()
                        logger.info(
                            f"Wind: {wind_state['speed_knots']:.1f}kn @ {wind_state['angle_deg']}° "
                            f"Batt={wind_state['battery']}%"
                        )

                # Subscribe to all wind-related notifications
                await client.start_notify(WIND_SPEED_CHAR_UUID, speed_callback)
                logger.info("Subscribed to wind speed")
                await client.start_notify(WIND_DIRECTION_CHAR_UUID, direction_callback)
                logger.info("Subscribed to wind direction")
                try:
                    await client.start_notify(BATTERY_CHAR_UUID, battery_callback)
                    logger.info("Subscribed to battery")
                except Exception:
                    logger.debug("Battery notifications not available")

                logger.info("Wind sensor connected and streaming")

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
            clear_wind_status()

        if running:
            logger.info(f"Reconnecting in {reconnect_interval}s...")
            await asyncio.sleep(reconnect_interval)

    csv_file.close()
    clear_wind_status()
    logger.info(f"Wind service stopped. {rows_written} rows written.")


def run(config):
    asyncio.run(run_async(config))


if __name__ == '__main__':
    config = load_config()
    if not config['wind']['enabled']:
        logger.info("Wind disabled in config, exiting")
        sys.exit(0)
    run(config)
