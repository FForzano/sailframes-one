#!/usr/bin/env python3
"""
analyze_tof.py - Time-of-Flight analysis with zero-crossing detection

Analyzes captured ADC data to precisely measure echo arrival time.
Uses envelope detection and zero-crossing interpolation for sub-sample accuracy.

Usage:
    python3 analyze_tof.py [port]

Or analyze a saved capture:
    python3 analyze_tof.py --file capture.csv
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import interp1d
import serial
import serial.tools.list_ports

# Configuration
BAUD_RATE = 115200
SAMPLE_RATE_HZ = 290000  # Calibrated: 5cm should be 146µs, was reading 265µs at 160kHz
SOUND_SPEED_MPS = 343.0  # Speed of sound at ~20°C
CARRIER_FREQ_HZ = 40000  # Ultrasonic carrier frequency
ADC_RESOLUTION = 4095
VREF = 3.3

# Detection parameters
ENVELOPE_THRESHOLD = 0.15  # Fraction of max envelope to detect FIRST arrival (lowered to catch early signal)
MIN_ZERO_CROSSINGS = 6     # Minimum crossings to average (QingStation uses 6)
NOISE_FLOOR_SAMPLES = 50   # First N samples to estimate noise level


def find_nucleo_port():
    """Auto-detect Nucleo serial port."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'usbmodem' in port.device.lower() or 'ttyACM' in port.device:
            return port.device
    return None


def parse_capture_from_serial(ser):
    """Read one capture from serial port."""
    lines = []
    in_capture = False

    while True:
        line = ser.readline().decode('utf-8', errors='ignore')
        if not line:
            continue
        if '--- BEGIN CAPTURE ---' in line:
            in_capture = True
            lines = []
            continue
        if in_capture:
            lines.append(line.strip())
        if '--- END CAPTURE ---' in line:
            break

    # Parse samples
    samples = []
    for line in lines:
        if ',' in line:
            try:
                idx, val = line.split(',')
                samples.append(int(val))
            except ValueError:
                pass
    return np.array(samples)


def compute_envelope(samples, sample_rate):
    """
    Compute signal envelope using Hilbert transform.
    Returns the amplitude envelope of the 40kHz carrier.
    """
    # Remove DC offset
    ac_signal = samples - np.mean(samples)

    # Hilbert transform gives analytic signal
    analytic = signal.hilbert(ac_signal)
    envelope = np.abs(analytic)

    # Smooth envelope with low-pass filter
    # Cutoff at ~5kHz (well below 40kHz carrier, above expected modulation)
    nyq = sample_rate / 2
    cutoff = 5000 / nyq
    if cutoff < 1:
        b, a = signal.butter(2, cutoff, btype='low')
        envelope = signal.filtfilt(b, a, envelope)

    return envelope, ac_signal


def find_echo_region_from_ac(ac_signal, sample_rate):
    """
    Find the FIRST ARRIVAL by looking at AC signal amplitude directly.
    More sensitive than envelope for detecting weak first arrivals.
    Returns (start_idx, end_idx, peak_idx)
    """
    # Calculate running RMS in windows (faster response than Hilbert envelope)
    window_size = int(sample_rate / CARRIER_FREQ_HZ)  # One 40kHz period
    if window_size < 3:
        window_size = 3

    # Simple running amplitude: max-min in sliding window
    running_amp = np.zeros(len(ac_signal))
    for i in range(window_size, len(ac_signal)):
        window = ac_signal[i-window_size:i]
        running_amp[i] = np.max(window) - np.min(window)

    # Estimate noise from early samples
    noise_region = running_amp[NOISE_FLOOR_SAMPLES:NOISE_FLOOR_SAMPLES+50]
    if len(noise_region) > 0:
        noise_level = np.mean(noise_region)
        noise_std = np.std(noise_region)
    else:
        noise_level = 0
        noise_std = 1

    # Threshold: 3x noise level or 20% of max, whichever detects signal first
    threshold = noise_level + 5 * noise_std

    # Find first point where amplitude exceeds threshold
    above_threshold = np.where(running_amp > threshold)[0]

    if len(above_threshold) == 0:
        # Fall back to percentage of max
        threshold = np.max(running_amp) * 0.15
        above_threshold = np.where(running_amp > threshold)[0]

    if len(above_threshold) == 0:
        return None, None, None

    start_idx = above_threshold[0]

    # End: where amplitude drops or after ~500µs (enough for several cycles)
    window_samples = int(500e-6 * sample_rate)  # 500µs window
    end_idx = min(start_idx + window_samples, len(ac_signal) - 1)

    # Peak within region
    peak_idx = start_idx + np.argmax(running_amp[start_idx:end_idx+1])

    return start_idx, end_idx, peak_idx


def find_echo_region(envelope, threshold_fraction=ENVELOPE_THRESHOLD):
    """
    Find echo region using envelope (kept for compatibility).
    Returns (start_idx, end_idx, peak_idx)
    """
    max_env = np.max(envelope)
    threshold = max_env * threshold_fraction

    above_threshold = np.where(envelope > threshold)[0]

    if len(above_threshold) == 0:
        return None, None, None

    start_idx = above_threshold[0]
    end_idx = above_threshold[-1]
    peak_idx = np.argmax(envelope)

    return start_idx, end_idx, peak_idx


def find_zero_crossings(ac_signal, start_idx, end_idx):
    """
    Find zero-crossing times within the echo region.
    Uses linear interpolation for sub-sample accuracy.
    Returns array of crossing times (in sample units, fractional).
    """
    crossings = []

    # Look for sign changes
    for i in range(start_idx, min(end_idx, len(ac_signal) - 1)):
        # Positive-going zero crossing (negative to positive)
        if ac_signal[i] <= 0 and ac_signal[i + 1] > 0:
            # Linear interpolation to find exact crossing
            # y = 0 at x = i + (-y0) / (y1 - y0)
            y0, y1 = ac_signal[i], ac_signal[i + 1]
            if y1 != y0:
                x_cross = i + (-y0) / (y1 - y0)
                crossings.append(x_cross)

    return np.array(crossings)


def analyze_zero_crossings(crossings, sample_rate, carrier_freq):
    """
    Analyze zero-crossings to verify they match expected carrier frequency
    and compute precise timing.
    """
    if len(crossings) < 2:
        return None

    # Time between crossings should be ~1/carrier_freq (one period)
    # But we only detect positive-going, so period = 1/freq
    expected_period_samples = sample_rate / carrier_freq

    # Calculate actual periods
    periods = np.diff(crossings)

    # Filter out outliers (should be close to expected period)
    valid_mask = np.abs(periods - expected_period_samples) < expected_period_samples * 0.3
    valid_periods = periods[valid_mask]

    if len(valid_periods) < 3:
        return None

    measured_freq = sample_rate / np.mean(valid_periods)

    return {
        'crossings': crossings,
        'periods': periods,
        'valid_periods': valid_periods,
        'measured_freq': measured_freq,
        'expected_freq': carrier_freq,
        'freq_error_pct': (measured_freq - carrier_freq) / carrier_freq * 100
    }


def compute_tof(crossings, sample_rate, num_crossings=MIN_ZERO_CROSSINGS):
    """
    Compute time-of-flight using the first N zero-crossings.
    QingStation averages 6 crossings for robustness.
    """
    if len(crossings) < num_crossings:
        num_crossings = len(crossings)

    if num_crossings == 0:
        return None

    # Average the first N crossing times
    avg_crossing = np.mean(crossings[:num_crossings])

    # Convert to time
    tof_seconds = avg_crossing / sample_rate

    return tof_seconds


def samples_to_distance(tof_seconds, sound_speed=SOUND_SPEED_MPS):
    """Convert time-of-flight to distance (one-way)."""
    return tof_seconds * sound_speed


def analyze_capture(samples, sample_rate=SAMPLE_RATE_HZ, plot=True):
    """
    Full analysis pipeline for one capture.
    Returns dict with timing results.
    """
    if len(samples) == 0:
        print("No samples to analyze!")
        return None

    # Time axis
    time_us = np.arange(len(samples)) / sample_rate * 1e6

    # Compute envelope
    envelope, ac_signal = compute_envelope(samples, sample_rate)

    # Find echo region using AC signal directly (more sensitive to weak first arrival)
    start_idx, end_idx, peak_idx = find_echo_region_from_ac(ac_signal, sample_rate)

    # If that fails, fall back to envelope method
    if start_idx is None:
        start_idx, end_idx, peak_idx = find_echo_region(envelope)

    if start_idx is None:
        print("Could not detect echo!")
        return None

    # Find zero crossings in echo region
    crossings = find_zero_crossings(ac_signal, start_idx, end_idx)

    # Analyze crossings
    crossing_analysis = analyze_zero_crossings(crossings, sample_rate, CARRIER_FREQ_HZ)

    # Compute time-of-flight
    tof = compute_tof(crossings, sample_rate)

    if tof is None:
        print("Could not compute ToF!")
        return None

    # Convert to distance
    distance = samples_to_distance(tof)

    # Results
    results = {
        'tof_us': tof * 1e6,
        'distance_mm': distance * 1000,
        'echo_start_us': start_idx / sample_rate * 1e6,
        'echo_peak_us': peak_idx / sample_rate * 1e6,
        'num_crossings': len(crossings),
        'crossing_analysis': crossing_analysis,
        'envelope_max': np.max(envelope),
    }

    # Print results
    print(f"\n{'='*50}")
    print(f"TIME-OF-FLIGHT ANALYSIS")
    print(f"{'='*50}")
    print(f"Echo detected: {results['echo_start_us']:.1f} - {end_idx/sample_rate*1e6:.1f} µs")
    print(f"Echo peak: {results['echo_peak_us']:.1f} µs")
    print(f"Zero crossings found: {results['num_crossings']}")
    if crossing_analysis:
        print(f"Measured carrier freq: {crossing_analysis['measured_freq']:.0f} Hz " +
              f"(error: {crossing_analysis['freq_error_pct']:+.1f}%)")
    print(f"\nTIME-OF-FLIGHT: {results['tof_us']:.2f} µs")
    print(f"DISTANCE: {results['distance_mm']:.1f} mm")
    print(f"{'='*50}\n")

    if plot:
        plot_analysis(samples, time_us, envelope, ac_signal,
                     start_idx, end_idx, peak_idx, crossings,
                     sample_rate, results)

    return results


def plot_analysis(samples, time_us, envelope, ac_signal,
                  start_idx, end_idx, peak_idx, crossings,
                  sample_rate, results):
    """Plot the analysis results."""

    fig, axes = plt.subplots(3, 1, figsize=(14, 10))

    # Plot 1: Raw signal with envelope
    ax1 = axes[0]
    ax1.plot(time_us, samples, 'b-', linewidth=0.5, alpha=0.7, label='Raw ADC')

    # Overlay envelope (scaled to ADC range)
    env_scaled = envelope / np.max(envelope) * (np.max(samples) - np.min(samples)) / 2
    env_offset = np.mean(samples)
    ax1.plot(time_us, env_scaled + env_offset, 'r-', linewidth=2, label='Envelope')

    # Mark echo region
    if start_idx is not None:
        ax1.axvline(x=time_us[start_idx], color='g', linestyle='--', label=f'Echo start')
        ax1.axvline(x=time_us[peak_idx], color='orange', linestyle='--', label=f'Echo peak')

    ax1.set_xlabel('Time (µs)')
    ax1.set_ylabel('ADC Value')
    ax1.set_title('Raw Signal with Envelope Detection')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Plot 2: AC signal with zero crossings
    ax2 = axes[1]
    voltage_mv = ac_signal * (VREF / ADC_RESOLUTION) * 1000
    ax2.plot(time_us, voltage_mv, 'b-', linewidth=0.5)
    ax2.axhline(y=0, color='k', linestyle='-', linewidth=0.5)

    # Mark zero crossings
    if len(crossings) > 0:
        crossing_times = crossings / sample_rate * 1e6
        ax2.scatter(crossing_times, np.zeros_like(crossing_times),
                   color='red', s=20, zorder=5, label=f'{len(crossings)} zero crossings')

    # Highlight echo region
    if start_idx is not None:
        ax2.axvspan(time_us[start_idx], time_us[min(end_idx, len(time_us)-1)],
                   alpha=0.2, color='green', label='Echo region')

    ax2.set_xlabel('Time (µs)')
    ax2.set_ylabel('AC Signal (mV)')
    ax2.set_title('AC Component with Zero-Crossing Detection')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    # Plot 3: Zoomed view of echo with crossings
    ax3 = axes[2]
    if start_idx is not None and len(crossings) > 0:
        # Zoom to echo region
        zoom_start = max(0, start_idx - 20)
        zoom_end = min(len(samples), end_idx + 20)

        ax3.plot(time_us[zoom_start:zoom_end],
                voltage_mv[zoom_start:zoom_end], 'b-', linewidth=1)
        ax3.axhline(y=0, color='k', linestyle='-', linewidth=0.5)

        # Mark crossings in zoom region
        for cx in crossings[:20]:  # First 20 crossings
            cx_time = cx / sample_rate * 1e6
            if time_us[zoom_start] <= cx_time <= time_us[zoom_end-1]:
                ax3.axvline(x=cx_time, color='red', linestyle=':', alpha=0.7)

        ax3.scatter(crossings[:20] / sample_rate * 1e6,
                   np.zeros(min(20, len(crossings))),
                   color='red', s=50, zorder=5, marker='o')

    ax3.set_xlabel('Time (µs)')
    ax3.set_ylabel('AC Signal (mV)')
    ax3.set_title(f'Zoomed Echo Region — ToF: {results["tof_us"]:.2f} µs = {results["distance_mm"]:.1f} mm')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('/Users/paul2/sailframes/wind_sensor/scripts/tof_analysis.png', dpi=150)
    print("Plot saved to tof_analysis.png")
    plt.show()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--file':
        # Load from file (future feature)
        print("File loading not yet implemented")
        return

    # Get serial port
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = find_nucleo_port()
        if port is None:
            print("No Nucleo board found. Specify port manually.")
            return

    print(f"Connecting to {port}...")
    ser = serial.Serial(port, BAUD_RATE, timeout=5)

    print("Waiting for capture...")
    print("(Press Ctrl+C to exit)\n")

    try:
        while True:
            samples = parse_capture_from_serial(ser)
            if len(samples) > 0:
                analyze_capture(samples, SAMPLE_RATE_HZ, plot=True)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ser.close()


if __name__ == '__main__':
    main()
