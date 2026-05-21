# RTCM3 / PPK — Architecture Archive

**Status:** Retired in firmware `2026.05.20.09`. Captured here for future revival.

## What was retired and why

The PPK (Post-Processed Kinematic) GNSS pipeline was the SailFrames strategic differentiator from 2026-03 through 2026-05-21. Boats captured raw RTCM3 MSM7 observations from the Waveshare LG290P at 1 Hz, uploaded the `.rtcm3` files to S3, and a cloud lambda paired them with free NOAA UFCORS base-station data via RTKLIB to produce sub-meter-accuracy positions for post-race analysis.

It was retired because:

- **10 Hz GPS fixes are more valuable than centimeter PPK accuracy** for SailFrames' primary use case (on-the-water OCS — over-the-line detection at race start — and per-tack motion analysis). At 5 kts a boat moves 2.5 m between 1 Hz fixes; you can't tell if it was on the right side of the line at exactly T+0.
- **The LG290P is mode-exclusive**: MSM observation output requires Base station mode (mode 2), which hard-locks the fix rate at 1 Hz per LG290P&LGx80P Protocol Spec v1.1 §2.3.28. Rover mode allows 10 Hz, but on firmware AANR01A06S the `PQTMCFGRTCM,W,7,…` command silently does not produce MSM frames in Rover mode despite the spec describing it as mode-agnostic. Empirically confirmed across E2 + E4 (22-minute car ride on `.07`, 1.5 KB `.rtcm3` files each, zero MSM7 frames — ephemeris only).
- **Future B1 hardware uses the LC29HEAMD chip**, which has a different command surface and a different PPK story; the LG290P-specific RTCM3 plumbing wouldn't carry forward without rework anyway.

The single firmware artifact lives on in [S3](http://sailframes-fleet-data-prod.s3.us-east-1.amazonaws.com/firmware/sailframes_e1_2026.05.20.08.bin) (sha256 `7d4afec346ab65625f7656a20d7c11e610d90ee6e902e3ea8dd79564d26d69cc`, git SHA `08cdadfe5d3f334b32e5d703f4e3319feff47df1`) and in git history — `git show 08cdadfe:edge-e/firmware/sailframes_e1/sailframes_e1.ino` retrieves the last fully-working PPK-era firmware source.

## Where to look for the code

Git SHAs (chronological order, last working PPK at the end):

| SHA | Description |
|---|---|
| `15a4970` and earlier | Original 1 Hz PPK era — full RTCM3 byte parser + frame counters + .rtcm3 upload path |
| `9608446` (`.07`) | Tested Rover mode — proved PQTMCFGRTCM does not emit MSM in Rover on AANR01A06S |
| `08cdadfe` (`.08`) | Final PPK build — Base mode + MSM7 + 1 Hz, the canonical revivable snapshot |
| `feature/drop-ppk-rtcm-go-10hz` HEAD (`.09`) | RTCM3 firmware code removed; this archive doc added |

To revive: branch off `08cdadfe`, cherry-pick or rebase forward whatever new features you want to keep, restore the affected hardware (or move to a GNSS chip that supports raw measurement output in a high-rate mode).

## Architecture as of `.08` (the snapshot worth preserving)

### LG290P configuration

Configured at every boot in `configureLG290P()`. Persists to NVM where possible; CFGRTCM does not persist and is re-issued every boot post-restart.

```
PQTMCFGRCVRMODE,W,2        # Base station mode — required for MSM emission
PQTMCFGPROT,W,1,3,…        # RTCM3 protocol enabled on UART3
PQTMCFGPROT,W,1,2,…        # RTCM3 protocol enabled on UART2 (ESP32 link)
PQTMCFGMSGRATE,W,GGA,1     # re-enable NMEA after base mode disabled it
PQTMCFGMSGRATE,W,RMC,1
PQTMCFGMSGRATE,W,GSA,1
PQTMCFGMSGRATE,W,GSV,1
PQTMCFGMSGRATE,W,RTCM3-1019,1   # GPS ephemeris
PQTMCFGMSGRATE,W,RTCM3-1020,1   # GLONASS ephemeris
PQTMCFGMSGRATE,W,RTCM3-1042,1   # BeiDou ephemeris
PQTMCFGMSGRATE,W,RTCM3-1046,1   # Galileo ephemeris
PQTMSAVEPAR                # persist mode + per-message rates
PQTMSRR                    # full restart applies base mode

# Post-restart, RAM-only:
PQTMCFGRTCM,W,7,0,-90,07,06,1,0   # Enable MSM7 + ephemeris streaming
# Re-send per-message rates (RTCM3-1019/1020/1042/1046) after restart
```

Result: 1 Hz emission of MSM7 (1077 GPS / 1087 GLONASS / 1097 Galileo / 1127 BeiDou) + ephemeris messages every ~30 seconds + station reference (1006) every 10 epochs.

### RTCM3 byte parser (firmware)

State machine in `readGPS()` separates RTCM3 frames from NMEA on the shared UART2 stream:

```cpp
struct RTCM3Parser {
    enum State { WAIT_SYNC, READ_HEADER, READ_PAYLOAD };
    State state = WAIT_SYNC;
    uint8_t header[3];
    int headerIdx = 0;
    uint16_t payloadLen = 0;
    uint8_t frameBuf[1200];
    int frameIdx = 0;
    int frameTotal = 0;
} rtcm;
```

Sync byte `0xD3`, then 3-byte header where low 10 bits of bytes 1-2 are payload length, then payload, then 3-byte CRC-24. Total frame = 3 + payload + 3. Message type = top 12 bits of payload (bytes 3-4).

The full frame including header + CRC was written verbatim to `<session>_raw.rtcm3` so RTKLIB could consume it directly via RTKCONV.

### SD card layout

```
/sf/YYYYMMDD/E1_YYYYMMDD_HHMMSS_nav.csv     # NMEA parsed
/sf/YYYYMMDD/E1_YYYYMMDD_HHMMSS_imu.csv     # BNO085 reports
/sf/YYYYMMDD/E1_YYYYMMDD_HHMMSS_wind.csv    # Calypso BLE (if paired)
/sf/YYYYMMDD/E1_YYYYMMDD_HHMMSS_pres.csv    # DPS310 (if present)
/sf/YYYYMMDD/E1_YYYYMMDD_HHMMSS_raw.rtcm3   # RTCM3 binary, the PPK source
```

### Upload path

The upload task tracked two counters — `pendingUploads` (CSVs) and `pendingRTCM` (`.rtcm3` files). `.rtcm3` files were only uploaded when the device was associated with the home SSID (`HOME_WIFI_SSID = "Home-IOT"`); on other networks (iPhone hotspot, yacht-club guest WiFi) they were skipped to avoid mobile-data overage. The TFT status bar showed `N3 R2` style counters indicating how many sessions had each kind of file still pending.

### PPK lambda (cloud side)

Independent of firmware. After every successful `.rtcm3` upload to S3:

1. Download `.rtcm3` from `s3://sailframes-fleet-data-prod/raw/<device>/<date>/<file>.rtcm3`
2. Convert RTCM3 → RINEX observation file using RTKCONV
3. Fetch matching base-station RINEX from NOAA UFCORS (free, ~1 hour latency) for the closest CORS station to the session location, time window matched
4. Fetch broadcast nav file (IGS) for the same period
5. Run RTKLIB's `rnx2rtkp` (or `rtkpost` for interactive) with PPK config to produce a fixed-ambiguity solution
6. Emit the high-accuracy positions back to S3 as a processed JSON for the dashboard to consume

Lambda code lived in `lambda/process_upload/` and `processing/`. That code is still in the repo as of `.09` but no longer fed by the device; either remove later or leave dormant.

### Known gotchas at retirement

- LG290P firmware AANR01A06S only emits MSM in Base station mode despite the spec describing PQTMCFGRTCM as mode-agnostic. If you revisit PPK and the firmware version on your device is different, retest Rover mode — the limitation may be firmware-specific.
- `PQTMCFGRTCM` does not persist in NVM. Must be re-sent every boot after the post-mode-switch restart.
- Base mode auto-disables NMEA output (§2.3.25), so explicit `PQTMCFGMSGRATE,W,GGA,1` etc. is required to re-enable NMEA after switching to base mode.
- `.rtcm3` files at 1 Hz with 4 constellations + ephemeris run roughly 500 B/s = 30 KB/min = 1.8 MB/h. The 1.9 MB OTA partition isn't relevant; the limit is upload time on weak WiFi.

## Hardware paths to revive PPK in the future

| Path | What it gets you |
|---|---|
| **Different LG290P firmware revision** | If a future Quectel release fixes the Rover-mode MSM bug, the current chip could do both 10 Hz + PPK |
| **External RTK-capable receiver** | u-blox ZED-F9P or similar — well-documented high-rate raw observation output, but expensive (~$200) and physically larger |
| **LC29HEAMD on B1 + investigation** | Quectel's LC29H series uses PAIR commands not PQTM; raw measurement support varies by SKU. Worth a separate investigation when B1 hardware ships |
| **Dual GNSS** | One LG290P in Base mode (1 Hz, PPK) + one in Rover mode (10 Hz, real-time) on the same boat. Doubles cost and antenna placement complexity |

Until one of these is viable, SailFrames is a **10 Hz high-precision GNSS + IMU motion analytics** platform, not a PPK platform.

---

*Archived 2026-05-21 alongside firmware `2026.05.20.09`. Last working PPK firmware: git `08cdadfe`.*
