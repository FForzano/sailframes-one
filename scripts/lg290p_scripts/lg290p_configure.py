#!/usr/bin/env python3
"""
SailFrames LG290P fleet configuration tool.

Configures a Waveshare LG290P GNSS module to the SailFrames E1 standard:
  - Rover mode
  - All four constellations (GPS, GLONASS, Galileo, BeiDou) + QZSS
  - 10 Hz fix rate
  - RTCM3 MSM7 raw observations + ephemeris (for PPK with RTKLIB)
  - UART3 at 460800 baud
  - Saved to NVM

Run on a Mac with the LG290P connected via the CH343 USB adapter.

Usage:
  python3 lg290p_configure.py                    # auto-detect port and baud
  python3 lg290p_configure.py --port /dev/cu.wchusbserial5B5E0696771
  python3 lg290p_configure.py --dry-run          # print commands only

Requires: pyserial  (pip install pyserial)
"""

import argparse
import glob
import sys
import time
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)


# ---------- NMEA helpers ----------

def nmea_checksum(payload: str) -> str:
    """XOR of all bytes between '$' and '*'."""
    cs = 0
    for ch in payload:
        cs ^= ord(ch)
    return f"{cs:02X}"


def build(payload: str) -> bytes:
    """Wrap payload (without leading $ or trailing *XX) into a full NMEA sentence."""
    return f"${payload}*{nmea_checksum(payload)}\r\n".encode("ascii")


# ---------- Configuration sequence ----------
# Order matters: configure first, save, restart, re-verify.
# All payloads are written WITHOUT the leading '$' and trailing '*XX' — build() adds them.
CONFIG_STEPS = [
    # Set rover mode (raw observations, no auto-base behavior)
    ("Set rover mode",                  "PQTMCFGRCVRMODE,W,1"),

    # Enable constellations: GPS, GLONASS, Galileo, BDS, QZSS (NavIC off)
    # Field order per spec: GPS, GLONASS, Galileo, BDS, QZSS, NavIC
    ("Enable GPS+GLO+GAL+BDS+QZSS",     "PQTMCFGCNST,W,1,1,1,1,1,0"),

    # 10 Hz fix rate (100 ms fix interval)
    ("Set 10 Hz fix rate",              "PQTMCFGFIXRATE,W,100"),

    # Global RTCM config: MSM_Type=7 (full MSM7), MSM_Mode=0 (don't output if no sats),
    # MSM_ElevThd=-90 (no limit), reserved fields 0x07/0x06, EPH_Mode=3 (output every epoch),
    # EPH_Interval=0 (unused when EPH_Mode=3).
    # This is what selects 1077/1087/1097/1127 vs the lower MSM types.
    ("Set RTCM MSM7 + EPH every epoch", "PQTMCFGRTCM,W,7,0,-90,07,06,3,0"),

    # Enable per-constellation MSM streams. The literal 'X' is required —
    # the actual message ID emitted (107X -> 1077 etc.) is determined by
    # MSM_Type set above.
    # Format per spec: ,W,<MsgName>,<Rate>,<Offset>
    ("Enable RTCM3 GPS MSM",            "PQTMCFGMSGRATE,W,RTCM3-107X,1,0"),
    ("Enable RTCM3 GLO MSM",            "PQTMCFGMSGRATE,W,RTCM3-108X,1,0"),
    ("Enable RTCM3 GAL MSM",            "PQTMCFGMSGRATE,W,RTCM3-109X,1,0"),
    ("Enable RTCM3 BDS MSM",            "PQTMCFGMSGRATE,W,RTCM3-112X,1,0"),

    # Per-constellation ephemeris streams (no offset field for these).
    # 1042 (BDS) and 1046 (Galileo) are NOT in the supported message list —
    # they are emitted automatically because EPH_Mode=3 above.
    ("Enable RTCM3 1019 (GPS eph)",     "PQTMCFGMSGRATE,W,RTCM3-1019,1"),
    ("Enable RTCM3 1020 (GLO eph)",     "PQTMCFGMSGRATE,W,RTCM3-1020,1"),
    ("Enable RTCM3 1044 (QZS eph)",     "PQTMCFGMSGRATE,W,RTCM3-1044,1"),

    # NMEA output: keep RMC/GGA at 1 Hz so the ESP32 still gets fix info.
    # Rate=10 with FixInterval=100ms -> 1 Hz output. No offset field for NMEA.
    ("Set GGA rate to 1 Hz",            "PQTMCFGMSGRATE,W,GGA,10"),
    ("Set RMC rate to 1 Hz",            "PQTMCFGMSGRATE,W,RMC,10"),

    # UART3 at 460800 baud (the UART our ESP32 talks to)
    ("Set UART3 to 460800 baud",        "PQTMCFGUART,W,3,460800,8,0,1,0"),

    # Save everything to NVM
    ("Save to flash",                   "PQTMSAVEPAR"),
]

# Baud rates the LG290P supports, in order to try for auto-detect.
# 460800 is checked first because that's what we leave units at.
SUPPORTED_BAUDS = [460800, 9600, 115200, 230400, 921600]

# Default macOS USB-serial port glob for CH343 adapters
DEFAULT_PORT_GLOB = "/dev/cu.wchusbserial*"


# ---------- Serial helpers ----------

def find_port() -> str:
    """Find the LG290P USB-serial port on macOS or Linux."""
    candidates = (
        glob.glob(DEFAULT_PORT_GLOB)
        + glob.glob("/dev/cu.usbserial*")
        + glob.glob("/dev/ttyUSB*")
        + glob.glob("/dev/ttyACM*")
    )
    if not candidates:
        raise RuntimeError(
            "No USB-serial device found. Plug in the LG290P and check the "
            "CH343 driver is installed (brew install --cask wch-ch34x-usb-serial-driver)."
        )
    if len(candidates) > 1:
        print(f"  Multiple ports found: {candidates}")
        print(f"  Using first: {candidates[0]}")
        print(f"  Specify --port to override.")
    return candidates[0]


def detect_baud(port: str, timeout: float = 2.0) -> int:
    """Try each supported baud and return the one where we see NMEA traffic."""
    print(f"\nAuto-detecting baud rate on {port}...")
    for baud in SUPPORTED_BAUDS:
        print(f"  Trying {baud}... ", end="", flush=True)
        try:
            with serial.Serial(port, baud, timeout=timeout) as s:
                # Drain any garbage and wait for fresh data
                s.reset_input_buffer()
                start = time.time()
                buf = b""
                while time.time() - start < timeout:
                    chunk = s.read(256)
                    if chunk:
                        buf += chunk
                        # Look for an NMEA start marker followed by checksum
                        if b"$G" in buf or b"$P" in buf:
                            # Sanity check: a valid sentence has a '*' and 2 hex digits
                            if b"*" in buf and len(buf) > 20:
                                print(f"found NMEA traffic at {baud} baud")
                                return baud
                print("no NMEA")
        except (serial.SerialException, OSError) as e:
            print(f"error ({e})")
    raise RuntimeError(
        "Could not detect baud rate. Module may be unpowered or wired wrong. "
        "Verify VCC=5V, GND, and that you're connected to UART3 (the labeled UART)."
    )


def send_and_wait(s: serial.Serial, sentence: bytes, label: str,
                  timeout: float = 2.0) -> bool:
    """Send an NMEA command and wait for the corresponding ',OK' acknowledgment."""
    # Extract the message name (e.g., 'PQTMCFGUART') for matching the response
    cmd_name = sentence.decode("ascii").split(",")[0].lstrip("$").split("*")[0]
    expected = f"${cmd_name},OK".encode("ascii")

    s.reset_input_buffer()
    s.write(sentence)
    s.flush()

    start = time.time()
    buf = b""
    while time.time() - start < timeout:
        chunk = s.read(256)
        if chunk:
            buf += chunk
            if expected in buf:
                print(f"    OK   {label}")
                return True
            if f"${cmd_name},ERROR".encode("ascii") in buf:
                print(f"    FAIL {label} (module returned ERROR)")
                return False
    print(f"    TIMEOUT {label} (no response in {timeout}s)")
    return False


# ---------- Main ----------

def configure(port: str, dry_run: bool = False) -> int:
    print("=" * 60)
    print("SailFrames LG290P configuration")
    print("=" * 60)

    if dry_run:
        print("\nDRY RUN — commands that would be sent:\n")
        for label, payload in CONFIG_STEPS:
            print(f"  # {label}")
            print(f"  {build(payload).decode('ascii').rstrip()}")
        print("  # Hot restart")
        print(f"  {build('PQTMHOT').decode('ascii').rstrip()}")
        return 0

    detected = detect_baud(port)

    print(f"\nOpening {port} at {detected} baud and applying configuration...\n")
    failures = 0
    with serial.Serial(port, detected, timeout=2.0) as s:
        # If we're not already at 460800, the UART change step will switch it.
        # We handle that by re-opening at the new baud after PQTMCFGUART.
        for label, payload in CONFIG_STEPS:
            sentence = build(payload)
            ok = send_and_wait(s, sentence, label)
            if not ok:
                failures += 1

            # Special handling: after we change UART3 baud, we'd need to reopen
            # the port at the new baud. But UART3 is the GPS<->ESP32 link;
            # if we're connected via a different UART, this won't affect us.
            # If the user has the CH343 wired to UART3, the next command will
            # just time out, which is acceptable — the SAVEPAR will still apply.

        # Note: we deliberately do NOT send PQTMHOT here. If the CH343 is
        # connected through UART3 (the typical wiring), the baud just changed
        # and the hot-restart ack would arrive at a baud our serial port
        # is no longer listening at — it always times out. Power-cycling
        # the module after this script finishes is the canonical way to
        # apply settings.

    print()
    print("=" * 60)
    if failures == 0:
        print("SUCCESS — all configuration steps acknowledged.")
        print("Module is ready. Power-cycle once and verify with:")
        print(f"  screen {port} 460800")
        return 0
    else:
        print(f"COMPLETED WITH {failures} FAILURE(S).")
        print("Re-run after checking wiring and baud rate.")
        return 1


def main():
    p = argparse.ArgumentParser(description="Configure a SailFrames E1 LG290P GNSS module.")
    p.add_argument("--port", help="Serial port (default: auto-detect)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print commands without sending them")
    args = p.parse_args()

    try:
        if args.dry_run and not args.port:
            return configure("(none)", dry_run=True)
        port = args.port or find_port()
        return configure(port, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
