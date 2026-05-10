#!/usr/bin/env python3
"""
plot_adc.py - Capture and plot ADC samples from STM32 ultrasonic burst mode

Connects to Nucleo serial port, waits for capture data, plots the waveform.
Look for echo pulse arrival to measure time-of-flight.

Usage:
    python3 plot_adc.py [port]

Example:
    python3 plot_adc.py /dev/cu.usbmodem14203
    python3 plot_adc.py  # auto-detect on macOS
"""

import sys
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Configuration
BAUD_RATE = 115200
ADC_RESOLUTION = 4095  # 12-bit ADC
VREF = 3.3  # Reference voltage

# Measured 2026-05-09 via PA1 GPIO-toggle probe in firmware:
# scope showed 667.97 kHz on the toggle → sample rate = 2 × 667.97 kHz.
# Matches the theoretical ceiling (80 MHz PCLK / DIV4 / 15 cycles = 1.333 MHz)
# almost exactly — the polling loop is ADC-bound, not CPU-bound.
# Earlier 290 kHz / 160 kHz / 50 kHz / 1.2 MHz figures were all wrong.
ESTIMATED_SAMPLE_RATE_HZ = 1335940  # 1.336 MHz, measured


def find_nucleo_port():
    """Auto-detect Nucleo serial port on macOS/Linux."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Nucleo boards typically show as usbmodem on macOS
        if 'usbmodem' in port.device.lower() or 'stlink' in port.description.lower():
            return port.device
        # On Linux, look for ttyACM
        if 'ttyACM' in port.device:
            return port.device
    return None


def parse_capture(lines):
    """Parse captured ADC data from serial output."""
    samples = []
    in_capture = False

    for line in lines:
        line = line.strip()
        if '--- BEGIN CAPTURE ---' in line:
            in_capture = True
            samples = []
            continue
        if '--- END CAPTURE ---' in line:
            in_capture = False
            break
        if in_capture and ',' in line:
            try:
                idx, val = line.split(',')
                samples.append(int(val))
            except ValueError:
                pass

    return np.array(samples)


def analyze_waveform(samples, sample_rate):
    """Analyze captured waveform for echo detection."""
    if len(samples) == 0:
        return {}

    # Convert to voltage
    voltage = samples * (VREF / ADC_RESOLUTION)

    # Calculate DC offset (average)
    dc_offset = np.mean(voltage)

    # Remove DC offset
    ac_signal = voltage - dc_offset

    # Find peak-to-peak amplitude
    vpp = np.max(voltage) - np.min(voltage)

    # Simple peak detection - find maximum absolute deviation from DC
    abs_signal = np.abs(ac_signal)
    peak_idx = np.argmax(abs_signal)
    peak_time_us = (peak_idx / sample_rate) * 1e6

    # Find where signal first exceeds threshold (echo arrival)
    threshold = 0.1  # 100mV threshold
    above_threshold = np.where(abs_signal > threshold)[0]
    if len(above_threshold) > 0:
        echo_start_idx = above_threshold[0]
        echo_time_us = (echo_start_idx / sample_rate) * 1e6
    else:
        echo_start_idx = None
        echo_time_us = None

    return {
        'dc_offset_v': dc_offset,
        'vpp': vpp,
        'peak_idx': peak_idx,
        'peak_time_us': peak_time_us,
        'echo_start_idx': echo_start_idx,
        'echo_time_us': echo_time_us,
        'ac_signal': ac_signal,
        'voltage': voltage
    }


def plot_capture(samples, analysis, sample_rate, save_path=None):
    """Plot the captured ADC waveform."""
    if len(samples) == 0:
        print("No samples to plot!")
        return

    # Time axis in microseconds
    time_us = np.arange(len(samples)) / sample_rate * 1e6

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    # Plot 1: Raw ADC values
    ax1 = axes[0]
    ax1.plot(time_us, samples, 'b-', linewidth=0.5)
    ax1.set_xlabel('Time (us)')
    ax1.set_ylabel('ADC Value (0-4095)')
    ax1.set_title('Raw ADC Capture - Ultrasonic Echo')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim([0, time_us[-1]])

    # Mark peak
    if analysis.get('peak_idx') is not None:
        ax1.axvline(x=analysis['peak_time_us'], color='r', linestyle='--',
                   label=f'Peak @ {analysis["peak_time_us"]:.1f} us')

    # Mark echo start
    if analysis.get('echo_time_us') is not None:
        ax1.axvline(x=analysis['echo_time_us'], color='g', linestyle='--',
                   label=f'Echo start @ {analysis["echo_time_us"]:.1f} us')

    ax1.legend()

    # Plot 2: Voltage with DC removed
    ax2 = axes[1]
    voltage = analysis.get('voltage', samples * (VREF / ADC_RESOLUTION))
    ac_signal = analysis.get('ac_signal', voltage - np.mean(voltage))

    ax2.plot(time_us, ac_signal * 1000, 'b-', linewidth=0.5)  # Convert to mV
    ax2.set_xlabel('Time (us)')
    ax2.set_ylabel('AC Signal (mV)')
    ax2.set_title(f'AC Component (DC removed) - Vpp: {analysis.get("vpp", 0)*1000:.1f} mV')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim([0, time_us[-1]])

    # Add horizontal threshold lines
    ax2.axhline(y=100, color='r', linestyle=':', alpha=0.5, label='100mV threshold')
    ax2.axhline(y=-100, color='r', linestyle=':', alpha=0.5)
    ax2.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"Plot saved to {save_path}")

    plt.show()


def main():
    # Get serial port
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = find_nucleo_port()
        if port is None:
            print("No Nucleo board found. Specify port manually.")
            print("Available ports:")
            for p in serial.tools.list_ports.comports():
                print(f"  {p.device}: {p.description}")
            sys.exit(1)

    print(f"Connecting to {port} at {BAUD_RATE} baud...")

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=5)
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        sys.exit(1)

    print("Waiting for capture data...")
    print("(Press Ctrl+C to exit)")

    capture_count = 0
    lines = []
    in_capture = False

    try:
        while True:
            line = ser.readline().decode('utf-8', errors='ignore')
            if not line:
                continue

            # Print status messages
            if 'Ultrasonic Burst Mode' in line or 'Burst:' in line:
                print(line.strip())
                continue

            if '--- BEGIN CAPTURE ---' in line:
                print("\nCapture started...")
                in_capture = True
                lines = [line]
                continue

            if in_capture:
                lines.append(line)

            if '--- END CAPTURE ---' in line:
                in_capture = False
                capture_count += 1
                print(f"Capture #{capture_count} complete ({len(lines)-2} lines)")

                # Parse and analyze
                samples = parse_capture(lines)
                if len(samples) > 0:
                    print(f"  Parsed {len(samples)} samples")

                    analysis = analyze_waveform(samples, ESTIMATED_SAMPLE_RATE_HZ)
                    print(f"  DC offset: {analysis['dc_offset_v']:.3f} V")
                    print(f"  Peak-to-peak: {analysis['vpp']*1000:.1f} mV")
                    if analysis['echo_time_us']:
                        print(f"  Echo arrival: {analysis['echo_time_us']:.1f} us")
                        # Calculate approximate distance
                        # Sound speed ~343 m/s at 20C
                        # Distance = time * speed / 2 (round trip)
                        distance_mm = (analysis['echo_time_us'] * 343 / 1e6) / 2 * 1000
                        print(f"  Estimated distance: {distance_mm:.1f} mm")

                    # Plot
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    save_path = f'/Users/paul2/sailframes/wind_sensor/scripts/capture_{timestamp}.png'
                    plot_capture(samples, analysis, ESTIMATED_SAMPLE_RATE_HZ, save_path)
                else:
                    print("  Failed to parse samples!")

                lines = []

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ser.close()


if __name__ == '__main__':
    main()
