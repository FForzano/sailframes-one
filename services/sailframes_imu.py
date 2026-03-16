#!/usr/bin/env python3
"""
SailFrames IMU Service
Reads BNO085 via I2C, logs heel/pitch/heading and linear acceleration.
"""

import os
import sys
import csv
import math
import time
import signal
import logging
from datetime import datetime, timezone
from pathlib import Path

import board
import busio
import adafruit_bno08x
from adafruit_bno08x.i2c import BNO08X_I2C
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [IMU] %(levelname)s %(message)s'
)
logger = logging.getLogger('sailframes.imu')

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


def get_data_dir(config):
    base = config['storage']['data_dir']
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    data_dir = Path(base) / today / 'imu'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def create_csv_writer(data_dir):
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filepath = data_dir / f'imu_{timestamp}.csv'
    f = open(filepath, 'w', newline='')
    writer = csv.writer(f)
    writer.writerow([
        'utc_time',
        'quat_i', 'quat_j', 'quat_k', 'quat_real',  # Rotation vector quaternion
        'heading_deg',       # Magnetic heading (0-360)
        'pitch_deg',         # Bow up/down (-90 to 90)
        'heel_deg',          # Roll port/starboard (-180 to 180)
        'accel_x_mps2',     # Linear acceleration X (forward)
        'accel_y_mps2',     # Linear acceleration Y (starboard)
        'accel_z_mps2',     # Linear acceleration Z (down)
        'accuracy',          # Rotation vector accuracy estimate (radians)
    ])
    logger.info(f"Logging to {filepath}")
    return f, writer


def quaternion_to_euler(i, j, k, real):
    """
    Convert quaternion to nautical Euler angles.
    Returns (heading, pitch, heel) in degrees.
    
    Heading: 0-360, 0=North, 90=East
    Pitch: -90 to 90, positive = bow up
    Heel: -180 to 180, positive = starboard heel
    """
    # Roll (heel) - rotation around X axis
    sinr_cosp = 2.0 * (real * i + j * k)
    cosr_cosp = 1.0 - 2.0 * (i * i + j * j)
    heel = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

    # Pitch - rotation around Y axis
    sinp = 2.0 * (real * j - k * i)
    if abs(sinp) >= 1:
        pitch = math.degrees(math.copysign(math.pi / 2, sinp))
    else:
        pitch = math.degrees(math.asin(sinp))

    # Yaw (heading) - rotation around Z axis
    siny_cosp = 2.0 * (real * k + i * j)
    cosy_cosp = 1.0 - 2.0 * (j * j + k * k)
    heading = math.degrees(math.atan2(siny_cosp, cosy_cosp))

    # Normalize heading to 0-360
    if heading < 0:
        heading += 360.0

    return heading, pitch, heel


def run(config):
    imu_config = config['imu']
    sample_rate = imu_config['sample_rate_hz']
    sample_interval = 1.0 / sample_rate

    logger.info(f"Initializing BNO085 on I2C bus {imu_config['i2c_bus']} "
                f"at address 0x{imu_config['i2c_address']:02X}")

    # Initialize I2C at 400kHz for BNO085
    i2c = busio.I2C(board.SCL, board.SDA, frequency=imu_config['i2c_frequency'])

    retries = 0
    bno = None
    while bno is None and running:
        try:
            bno = BNO08X_I2C(i2c, address=imu_config['i2c_address'])
            logger.info("BNO085 connected")
        except Exception as e:
            retries += 1
            if retries % 5 == 0:
                logger.warning(f"BNO085 not responding: {e}")
            time.sleep(2)

    if not running:
        return

    # Enable sensor reports
    bno.enable_feature(adafruit_bno08x.BNO_REPORT_ROTATION_VECTOR)
    bno.enable_feature(adafruit_bno08x.BNO_REPORT_LINEAR_ACCELERATION)
    logger.info("Sensor reports enabled: rotation_vector, linear_acceleration")

    data_dir = get_data_dir(config)
    csv_file, writer = create_csv_writer(data_dir)
    rows_written = 0

    try:
        while running:
            loop_start = time.monotonic()

            try:
                quat = bno.quaternion
                linear_accel = bno.linear_acceleration
            except Exception as e:
                logger.warning(f"Read error: {e}")
                time.sleep(0.1)
                continue

            if quat is None or any(q is None for q in quat):
                time.sleep(0.01)
                continue

            i, j, k, real = quat
            heading, pitch, heel = quaternion_to_euler(i, j, k, real)

            ax, ay, az = linear_accel if linear_accel else (0, 0, 0)

            # Get accuracy estimate if available
            accuracy = ''
            try:
                accuracy = bno.quaternion_accuracy
            except Exception:
                pass

            utc_now = datetime.now(timezone.utc).isoformat()
            writer.writerow([
                utc_now,
                f"{i:.6f}", f"{j:.6f}", f"{k:.6f}", f"{real:.6f}",
                f"{heading:.2f}",
                f"{pitch:.2f}",
                f"{heel:.2f}",
                f"{ax:.4f}", f"{ay:.4f}", f"{az:.4f}",
                f"{accuracy}" if accuracy != '' else '',
            ])
            rows_written += 1

            if rows_written % 500 == 0:
                csv_file.flush()

            # Rotate at midnight
            current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if data_dir.parent.name != current_date:
                csv_file.close()
                data_dir = get_data_dir(config)
                csv_file, writer = create_csv_writer(data_dir)
                rows_written = 0

            # Maintain sample rate
            elapsed = time.monotonic() - loop_start
            sleep_time = sample_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        csv_file.close()
        logger.info(f"IMU service stopped. {rows_written} rows written.")


if __name__ == '__main__':
    config = load_config()
    if not config['imu']['enabled']:
        logger.info("IMU disabled in config, exiting")
        sys.exit(0)
    run(config)
