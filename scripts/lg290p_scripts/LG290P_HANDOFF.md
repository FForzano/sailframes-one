# LG290P Fleet Configuration — Claude Code Handoff

**Status:** First module successfully configured (boat unit, baud 460800, all 15 PQTM steps acknowledged). Four more units pending. Firmware bootstrap module written but not yet wired into E1 firmware.

**Hardware:** Waveshare LG290P quad-band GNSS modules (5 fresh units), connected to Mac via CH343 USB-UART adapter at `/dev/cu.wchusbserial5B5E0697051` (port suffix varies per cable).

**Goal:** Bring all 5 modules up to SailFrames E1 fleet standard, then integrate the bootstrap routine into the E1 firmware as a field-recovery path.

---

## What the configuration does

Configures each LG290P for SailFrames PPK workflow:

| Setting | Value | PQTM command |
|---|---|---|
| Receiver mode | Rover | `PQTMCFGRCVRMODE,W,1` |
| Constellations | GPS+GLO+GAL+BDS+QZSS (NavIC off) | `PQTMCFGCNST,W,1,1,1,1,1,0` |
| Fix rate | 10 Hz | `PQTMCFGFIXRATE,W,100` |
| RTCM MSM type | MSM7 + ephemeris every epoch | `PQTMCFGRTCM,W,7,0,-90,07,06,3,0` |
| RTCM observations | GPS/GLO/GAL/BDS MSM7 (1077/1087/1097/1127), every epoch | `PQTMCFGMSGRATE,W,RTCM3-107X,1,0` (per constellation) |
| RTCM ephemeris | 1019/1020/1044, every epoch (1042/1046 auto via EPH_Mode=3) | `PQTMCFGMSGRATE,W,RTCM3-1019,1` etc. |
| NMEA GGA/RMC | 1 Hz (rate=10 with 100ms fix interval) | `PQTMCFGMSGRATE,W,GGA,10` |
| UART3 baud | 460800 | `PQTMCFGUART,W,3,460800,8,0,1,0` |
| NVM | Saved | `PQTMSAVEPAR` |

Output stream after configuration: binary RTCM3 frames (D3 magic byte) at 10 Hz interleaved with 1 Hz `$GNRMC`/`$GNGGA` on UART3 at 460800 baud. Suitable for PPK with RTKLIB (RTKCONV → RTKPOST) using NOAA CORS base stations.

---

## Two deliverables already exist

### 1. `lg290p_configure.py` — Mac-side fleet rollout tool

Auto-detects baud rate (tries 460800, 9600, 115200, 230400, 921600), sends all 15 PQTM commands, waits for each `,OK` ack, saves to NVM. Verified working on first unit. Needs `pyserial` and CH343 driver (`brew install --cask wch-ch34x-usb-serial-driver`).

```bash
python3 lg290p_configure.py                # auto-detect everything
python3 lg290p_configure.py --port /dev/cu.wchusbserial...
python3 lg290p_configure.py --dry-run      # print without sending
```

Per-unit time: ~30 seconds. Power-cycle after script completes.

### 2. `lg290p_bootstrap.h` — ESP32 firmware drop-in

Header-only C++ module that runs the identical sequence over UART2 when `gps_bootstrap=1` is present in `/config.txt` on the SD card. On success, clears the flag and reboots. Not yet integrated into the E1 firmware.

**Both files are intentionally kept in lockstep** — `CONFIG_STEPS` in the Python script and `kConfigSteps` in the header are the same sequence. Any future change must update both.

---

## Spec-derived facts that bit me on first attempt

These are documented in the LG290P GNSS Protocol Specification v1.0.0 and worth keeping in mind for future PQTM work:

1. **MSM rates are per-constellation, not per-message-ID.** The supported names are literally `RTCM3-107X`, `RTCM3-108X`, `RTCM3-109X`, `RTCM3-112X` (with capital X). The actual ID emitted (1077 vs 1074 etc.) is determined globally by `MSM_Type` in `PQTMCFGRTCM`.

2. **The `<MsgVer/Offset>` field is omitted for non-MSM RTCM and standard NMEA.** Adding `,0` to `RTCM3-1019,1` or `GGA,10` returns ERROR. Only MSM messages and PQTM messages with versions take the third parameter.

3. **`RTCM3-1042` and `RTCM3-1046` are NOT in the supported `PQTMCFGMSGRATE` list.** BDS and Galileo ephemeris are emitted automatically when `PQTMCFGRTCM`'s `EPH_Mode=3` is set. Only `1019`, `1020`, `1041`, `1044` are individually configurable.

4. **`PQTMHOT` after `PQTMCFGUART,W,3,...` always times out** when the CH343 is connected through UART3 — the ack arrives at the new baud and the host's serial port is no longer listening. The script intentionally omits the hot restart and relies on user power-cycle. This is fine because `PQTMSAVEPAR` already persisted everything.

5. **Checksum is XOR of bytes between `$` and `*`**, two ASCII hex chars uppercase. The Python implementation is verified against four documented examples (`PQTMSAVEPAR*5A`, `PQTMRESTOREPAR*13`, `PQTMCFGRCVRMODE,W,2*29`, `PQTMCFGRTK,W,1,1*6C`).

---

## Remaining work for Claude Code

### Phase 1 — Fleet rollout (no code changes needed)

Configure the remaining 4 modules. Per unit:

1. Wire LG290P UART3 to CH343 adapter (5V, GND, TX→RX, RX→TX), antenna connected.
2. `python3 lg290p_configure.py`
3. Power-cycle.
4. Verify with `screen /dev/cu.wchusbserial... 460800` — look for binary frames (D3 magic byte) plus 1 Hz NMEA.
5. Label unit with boat ID (E1-02 through E1-05).

This is just running the script 4 more times. No engineering involved unless something fails.

### Phase 2 — Wire `lg290p_bootstrap.h` into E1 firmware

**Where it goes:** The bootstrap call belongs in `setup()` after SD initialization succeeds and before normal sensor task spawning. Pattern:

```cpp
#include "lg290p_bootstrap.h"

void setup() {
    Serial.begin(115200);

    // SD must be ready before we can read or rewrite config.txt
    if (!SD.begin(SD_CS_PIN)) {
        Serial.println("SD init failed - skipping bootstrap check");
    } else {
        // GPS UART must be open so the bootstrap can talk to it
        Serial2.begin(460800, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

        if (LG290P_Bootstrap::isRequested("/config.txt")) {
            int failures = LG290P_Bootstrap::run(Serial2, "/config.txt",
                                                 GPS_RX_PIN, GPS_TX_PIN);
            if (failures == 0) {
                Serial.println("Bootstrap success - rebooting");
                delay(500);
                ESP.restart();
            } else {
                Serial.printf("Bootstrap had %d failures - flag retained\n", failures);
                // Continue to normal boot; user can investigate via serial
            }
        }
    }

    // ...rest of normal setup (BNO085, OLED, FreeRTOS task pinning, etc.)
}
```

**Pin defines to use:** Match the existing E1 firmware constants — UART2 is GPIO16 (RX) / GPIO17 (TX) per the wiring in CLAUDE.md.

**Edge cases worth handling:**

- **Bootstrap fails partway through** — flag should NOT be cleared so the next reboot retries. Already handled in `lg290p_bootstrap.h::run()` which only calls `clearRequest()` when `failures == 0`.
- **SD read of config.txt fails** — `isRequested()` returns false, normal boot proceeds. This is correct behavior; we don't want to block boot on a missing/corrupt config.
- **OLED / Wi-Fi state during bootstrap** — bootstrap takes ~30 seconds. Consider showing "GPS BOOTSTRAP" on the OLED during this period so the user knows the unit isn't hung. Add an optional callback parameter to `run()` for status display, or accept that the unit looks frozen for 30 seconds (acceptable since bootstrap is rare).
- **Existing Serial2 configuration in main firmware** — make sure the bootstrap runs before any other task starts reading from Serial2, otherwise responses get consumed by the wrong reader.

### Phase 3 — Documentation in CLAUDE.md

Add a "GPS bootstrap recovery" section describing:

- When to set `gps_bootstrap=1` in config.txt (after replacing an LG290P, after factory reset, after any unexplained behavior)
- The 30-second wait period and what success looks like
- How to verify success (line is automatically removed from config.txt after run)
- How to recover if bootstrap fails (check serial console output, verify wiring, retry)

Cross-reference: this is the field-recovery counterpart to the Python script which is for bench rollout.

### Phase 4 — Test scenarios

Before declaring the bootstrap integration done:

1. **Happy path:** Add `gps_bootstrap=1` to a known-good unit's config.txt, power-cycle, verify all 15 steps ack OK, verify flag is removed, verify GPS comes up correctly after reboot.
2. **Already-configured unit:** Run bootstrap on a unit that's already in spec. Should succeed (commands are idempotent — setting rover mode on a rover is fine).
3. **Garbage in config.txt:** Set `gps_bootstrap=1` with a malformed config.txt. Bootstrap should still trigger; main firmware should handle config absence gracefully.
4. **Power loss mid-bootstrap:** Pull power 5 seconds into the sequence. On next boot, flag should still be set, bootstrap should retry, end state should be correct.

---

## Files in repo

```
sailframes/
├── lg290p_scripts/
│   ├── lg290p_configure.py       # Mac-side rollout tool (working)
│   ├── lg290p_bootstrap.h        # Firmware bootstrap module (not yet integrated)
│   └── README.md                 # User-facing docs
└── e1_firmware/
    └── (existing firmware — bootstrap.h needs wiring in here)
```

---

## Open questions for Claude Code

1. **Should bootstrap also run if `Serial2.begin()` succeeded but no NMEA is detected after 5 seconds of normal boot?** Could be a useful "auto-recovery" trigger but risks false positives if the GPS just hasn't acquired yet. Recommend NO for now — keep bootstrap manual-only via the flag.

2. **Should `clearRequest()` be more robust?** Current implementation reads the file, filters out the flag line, deletes the file, rewrites it. If power dies between delete and rewrite, config.txt is lost. Consider: write to `/config.txt.new`, fsync, rename. SD library on ESP32 doesn't have atomic rename, so a more cautious approach: write `/config.txt.new`, then on success delete original and rename. Or simpler: just write `/config.txt.bak` before rewriting.

3. **Should the firmware version log the LG290P firmware version after bootstrap?** Add a `PQTMVERNO` query at the end of `run()` and log the response, so SD logs capture which LG290P firmware revision the unit is running. Useful for fleet diagnostics.

---

## Reference

- LG290P GNSS Protocol Specification v1.0.0 (2024-05-17), Quectel — definitive PQTM command reference
- SparkFun LG290P breakout docs at `docs.sparkfun.com/SparkFun_LG290P_Quadband_GNSS_RTK_Breakout/pqmt_commands/` — useful but incomplete; defer to Quectel spec on conflicts
- RTKLIB documentation for the downstream PPK workflow
- NOAA CORS UFCORS at `geodesy.noaa.gov/UFCORS` for base station data
