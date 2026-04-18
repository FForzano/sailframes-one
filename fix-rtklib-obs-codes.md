# Task: Fix RTKLIB Observation Code Mapping for PPK Processing

## Context

SailFrames PPK processing pipeline is getting 0% fix rate (100% single-point Q=5 solutions) despite having compatible L2C signals on both rover and base station. The problem is **not** signal incompatibility — it's observation code mapping between RINEX 2 (base) and RINEX 3 (rover).

## The Discovery

The MAMI CORS base station (Leica GR50) RINEX 2 header shows:

```
9    C1    L1    D1    S1    P2    L2    D2    S2    C2    # / TYPES OF OBSERV
```

Key: **Both `P2` (L2 P(Y)) and `C2` (L2C civilian) are present.** The GR50 tracks L2C.

The E1 rover (Quectel LG290P) outputs RTCM3 which RTKCONV converts to RINEX 3 with codes:
- `C1C`, `L1C` — L1 C/A (compatible with base `C1`/`L1`)
- `C2X`, `L2X` — L2C (compatible with base `C2`/`L2`, but RTKLIB may not be matching them)

## Root Cause

RTKLIB's stock code may not automatically match RINEX 2 observation codes (`C2`/`L2`) to RINEX 3 codes (`C2X`/`L2X`) when processing mixed-version files. This means dual-frequency observations exist on both sides but aren't being used for double-difference formation.

## What Needs to Change

### 1. Switch to RTKExplorer's demo5 fork of RTKLIB

The demo5 fork (https://github.com/rtklibexplorer/RTKLIB) has significantly better handling of:
- Mixed RINEX 2/3 observation code matching
- Consumer-grade receiver support
- GLONASS ambiguity resolution with mixed receiver types

**Action:** Replace stock RTKLIB in the Lambda Docker image with the demo5 b34k fork.

Current Lambda location: `lambda/ppk_process/`
The Lambda uses a Docker image that includes RTKLIB binaries (`rnx2rtkp` or `rtkpost`).

Check the Dockerfile for how RTKLIB is currently built/installed and replace with:
```bash
git clone -b demo5 https://github.com/rtklibexplorer/RTKLIB.git
cd RTKLIB/app/consapp/rnx2rtkp/gcc
make
```

### 2. Update ppk.conf for Dual-Frequency Processing

Current config (from `lambda/ppk_process/ppk.conf`) has:
```ini
pos1-frequency     =l1           # Was set to L1-only because of assumed L2 incompatibility
```

Change to:
```ini
pos1-frequency     =l1+l2        # Enable dual-frequency — L2C is compatible
```

### 3. Verify RTKCONV Output

Check how the Lambda converts RTCM3 → RINEX. The conversion step (RTKCONV / `convbin`) should be outputting RINEX 3 format. Verify:
- The rover RINEX output contains `C2X`/`L2X` (not just `C2S` or `C2L`)
- The `-od` flag is set for Doppler observations
- The `-os` flag is set for SNR observations

Look in `handler.py` for the RTKCONV/convbin command and check its arguments.

### 4. Add Observation Code Priority Configuration

In ppk.conf, add explicit observation code priority to help RTKLIB match codes:
```ini
# Observation code priority for GPS L2
pos1-codepri_gps_l2  =XSLWPYMCQ
```

This tells RTKLIB to prefer L2C codes (X, S, L) over P(Y) codes (W, P, Y) when matching observations.

### 5. Ensure Multiple CORS Hourly Files Are Downloaded

The sailing session on April 7 ran 17:53–20:19 UTC, spanning hours 17–20. Verify that `cors_download/handler.py` downloads ALL required hourly files and concatenates them:
- `mami097r.26o` (hour 17)
- `mami097s.26o` (hour 18)
- `mami097t.26o` (hour 19)
- `mami097u.26o` (hour 20)

Check the current code — if it only downloads a single hourly file, the rover has no base data for most of the session, producing Q=0 for those epochs.

### 6. Fix GPS Ephemeris (1019) in E1 Firmware (Separate Task)

The RTCM3 files are missing GPS ephemeris messages (1019). The IGS broadcast nav file workaround is fine for now, but the root cause should be investigated:
- Check if `sendPQTM("PQTMCFGMSGRATE,W,RTCM3-1019,1")` gets an ACK response
- Log the response after sending the command
- Verify 1019 messages appear in serial output during recording

This is a firmware issue, not a Lambda issue — handle separately.

## Files to Modify

| File | Changes |
|------|---------|
| `lambda/ppk_process/Dockerfile` | Replace stock RTKLIB with demo5 fork |
| `lambda/ppk_process/ppk.conf` | `pos1-frequency=l1+l2`, add code priority settings |
| `lambda/ppk_process/handler.py` | Verify RTKCONV args, check RINEX output codes |
| `lambda/cors_download/handler.py` | Verify multi-hour file download and concatenation |

## Validation

After changes, reprocess the April 7 session (E1, 17:53–20:19 UTC, CORS station MAMI):

```bash
aws lambda invoke --profile sailframes --region us-east-1 \
    --function-name sailframes-ppk-process \
    --cli-binary-format raw-in-base64-out \
    --payload '{"device_id":"E1","folder":"2026-04-07","date":"2026-04-07","cors_station":"mami"}' \
    /tmp/result.json
```

**Success criteria:**
- Fix rate > 50% (Q=1)
- Float rate for remaining (Q=2)
- Accuracy < 1m horizontal
- Points count ≈ 8,700 (145 min × 1Hz)

## Reference

- MAMI station: Massachusetts Maritime Academy, Leica GR50, RINEX 2.11
- MAMI RINEX obs codes: C1, L1, D1, S1, P2, L2, D2, S2, C2
- Rover RINEX 3 obs codes: C1C, L1C, C2X, L2X
- RTKExplorer demo5: https://github.com/rtklibexplorer/RTKLIB
- NOAA UFCORS: https://geodesy.noaa.gov/UFCORS/
- Current ppk.conf: see `lambda/ppk_process/ppk.conf` in repo
