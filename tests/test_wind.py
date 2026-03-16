#!/usr/bin/env python3
"""Test Calypso Mini BLE wind sensor - scan and read data."""

import asyncio

print("=== SailFrames Wind Sensor Test ===\n")

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("✗ Missing library: bleak")
    print("  Run: pip3 install bleak --break-system-packages")
    exit(1)


CALYPSO_WIND_CHAR_UUID = "0000a001-0000-1000-8000-00805f9b34fb"


async def scan():
    print("Scanning for BLE devices (30 seconds)...\n")
    devices = await BleakScanner.discover(timeout=30)

    calypso_found = None
    print(f"Found {len(devices)} BLE devices:\n")

    for d in sorted(devices, key=lambda x: x.rssi, reverse=True):
        name = d.name or "Unknown"
        is_calypso = 'calypso' in name.lower() or 'ultrasonic' in name.lower()
        marker = " ← CALYPSO" if is_calypso else ""
        print(f"  {d.address}  RSSI={d.rssi:4d}  {name}{marker}")
        if is_calypso:
            calypso_found = d

    if calypso_found:
        print(f"\n✓ Calypso found: {calypso_found.name} at {calypso_found.address}")
        print(f"\n  Set this in config: ble_mac_address: \"{calypso_found.address}\"")

        # Try to connect and read
        print(f"\n  Attempting to connect...")
        try:
            async with BleakClient(calypso_found.address, timeout=20) as client:
                print(f"  ✓ Connected!")

                # List services
                print(f"\n  Available services:")
                for service in client.services:
                    print(f"    {service.uuid}: {service.description}")
                    for char in service.characteristics:
                        props = ','.join(char.properties)
                        print(f"      {char.uuid} [{props}]")

                # Try to read wind data
                print(f"\n  Listening for wind data (10 seconds)...")
                data_received = []

                def callback(sender, data):
                    data_received.append(data)
                    print(f"    Received: {data.hex()} ({len(data)} bytes)")

                try:
                    await client.start_notify(CALYPSO_WIND_CHAR_UUID, callback)
                    await asyncio.sleep(10)
                    await client.stop_notify(CALYPSO_WIND_CHAR_UUID)
                except Exception as e:
                    print(f"    Could not subscribe to wind data: {e}")
                    print(f"    The UUID may differ on your firmware version.")
                    print(f"    Check the service list above for the correct characteristic.")

                if data_received:
                    print(f"\n  ✓ Wind data flowing! Received {len(data_received)} packets.")
                else:
                    print(f"\n  ✗ Connected but no wind data received.")
                    print(f"    Make sure the Calypso is powered on and in BLE mode.")

        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
    else:
        print("\n✗ No Calypso device found.")
        print("  Make sure the Calypso Mini is:")
        print("  - Powered on (blue LED)")
        print("  - Not connected to another device (phone app, etc.)")
        print("  - Within 30m range")


asyncio.run(scan())
