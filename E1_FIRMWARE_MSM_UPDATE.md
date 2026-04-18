# SailFrames E1 — Firmware Update: RTCM3 MSM Observation Support

## Date: April 6, 2026 (Final)

---

## Summary

The LG290P must be set to **base station mode** to output RTCM3 MSM observation messages.
NMEA messages (GGA, RMC) are re-enabled manually for the OLED display (SOG, COG).
PPK post-processing uses the MSM4 raw observations with RTKLIB.

**Firmware version:** LG290P03AANR02A01S (v2.01, 2025/12/12)

---

## Architecture

```
LG290P (Base Station Mode)
  ├── RTCM3 MSM4 observations → SD card (.rtcm3) → PPK post-processing
  ├── RTCM3 ephemeris (1019/1020/1042/1046) → SD card (.rtcm3)
  ├── RTCM3 reference (1005/1033) → SD card (.rtcm3)
  └── NMEA (GGA/RMC) → ESP32 parser → OLED display (SOG, COG)
```

The OLED only shows **SOG** (speed over ground) and **COG** (course over ground), both
derived from Doppler measurements in the RMC message. These work correctly in base
station mode because Doppler is a raw satellite observation independent of the position
solution algorithm.

PPK recomputes centimeter-level positions post-race from the MSM4 raw observations.
The NMEA position is not used for analytics.

---

## RTCM3 Messages Output

### MSM4 Observations (confirmed working)

| Message | Constellation | Content |
|---------|--------------|---------|
| 1074 | GPS | Pseudorange + carrier phase |
| 1084 | GLONASS | Pseudorange + carrier phase |
| 1094 | Galileo | Pseudorange + carrier phase |
| 1124 | BeiDou | Pseudorange + carrier phase |

### Supporting Messages

| Message | Content | How enabled |
|---------|---------|-------------|
| 1005 | Station reference position | Auto in base mode |
| 1033 | Receiver/antenna info | Auto in base mode |
| 1019 | GPS ephemeris | PQTMCFGMSGRATE |
| 1020 | GLONASS ephemeris | PQTMCFGMSGRATE |
| 1042 | BeiDou ephemeris | PQTMCFGMSGRATE |
| 1046 | Galileo ephemeris | PQTMCFGMSGRATE |

### MSM7 Status

CFGRTCM accepts MSM type 7 and reads back as 7, but actual output is MSM4
(1074/1084/1094/1124). This is a known firmware behavior. MSM4 is sufficient for
centimeter-level PPK with RTKLIB.

---

## PQTMCFGRTCM Command

```
$PQTMCFGRTCM,W,7,0,-90,07,06,1,0
               │  │   │   │   │  │  │
               │  │   │   │   │  │  └─ ephemeris interval: 0 = immediate
               │  │   │   │   │  └──── ephemeris mode: 1 = output on update
               │  │   │   │   └─────── signal mask: 06 = L1 + L2
               │  │   │   └────────── constellation mask: 07 = GPS + GLO + GAL
               │  │   └───────────── elevation mask: -90° = no minimum
               │  └────────────────── reserved: always 0
               └───────────────────── MSM type: 7 = request MSM7 (gets MSM4)
```

**This command only works in base station mode (receiver mode 2).**

**This command does NOT persist across power cycles.** The ESP32 firmware must
send it after every boot.

---

## Firmware Startup Sequence

The ESP32 firmware must configure the LG290P on every boot:

```cpp
void configureLG290P() {
  // Step 1: Wait for LG290P to boot
  delay(3000);
  
  // Drain any buffered data
  while (Serial2.available()) Serial2.read();
  
  // Step 2: Re-enable NMEA messages (safety net — also saved in NVM)
  sendPQTM("PQTMCFGMSGRATE,W,GGA,1");
  delay(100);
  sendPQTM("PQTMCFGMSGRATE,W,RMC,1");
  delay(100);
  
  // Step 3: Send CFGRTCM for MSM output
  // MUST be sent every boot — does not persist in NVM
  // Do NOT save or restart after this command
  sendPQTM("PQTMCFGRTCM,W,7,0,-90,07,06,1,0");
  delay(200);
  
  // Step 4: Verify
  sendPQTM("PQTMCFGRTCM,R");
  delay(200);
  
  Serial.println("[GPS] Configuration complete");
}
```

**Critical rules:**
- Do NOT send `$PQTMSAVEPAR` after CFGRTCM
- Do NOT send `$PQTMSRR` or `$PQTMHOT` after CFGRTCM
- CFGRTCM must be the LAST command — nothing after it restarts or saves

---

## One-Time QGNSS Setup (Already Done)

These settings are saved in NVM and persist across power cycles.
Only redo if module is factory reset.

```
$PQTMCFGRCVRMODE,W,2          ← base station mode
$PQTMSAVEPAR
$PQTMSRR
                               ← wait 6-8 seconds for reconnect
$PQTMCFGMSGRATE,W,GGA,1       ← re-enable NMEA (off by default in base mode)
$PQTMCFGMSGRATE,W,RMC,1
$PQTMCFGMSGRATE,W,GSA,1
$PQTMCFGMSGRATE,W,GSV,1
$PQTMCFGMSGRATE,W,RTCM3-1019,1  ← GPS ephemeris
$PQTMCFGMSGRATE,W,RTCM3-1020,1  ← GLONASS ephemeris
$PQTMCFGMSGRATE,W,RTCM3-1042,1  ← BeiDou ephemeris
$PQTMCFGMSGRATE,W,RTCM3-1046,1  ← Galileo ephemeris
$PQTMSAVEPAR
                               ← do NOT save or restart after next command
$PQTMCFGRTCM,W,7,0,-90,07,06,1,0  ← MSM output (RAM only)
```

Use CheckNum button in QGNSS for all commands.

---

## RTCM3 Parser

### Stats Struct

```cpp
struct RTCM3Stats {
  // MSM4 (confirmed working — primary PPK data)
  uint32_t msm4_gps = 0;   // 1074
  uint32_t msm4_glo = 0;   // 1084
  uint32_t msm4_gal = 0;   // 1094
  uint32_t msm4_bds = 0;   // 1124
  
  // MSM7 (future — currently firmware outputs MSM4 instead)
  uint32_t msm7_gps = 0;   // 1077
  uint32_t msm7_glo = 0;   // 1087
  uint32_t msm7_gal = 0;   // 1097
  uint32_t msm7_bds = 0;   // 1127
  
  // Ephemeris
  uint32_t eph_gps = 0;    // 1019
  uint32_t eph_glo = 0;    // 1020
  uint32_t eph_bds = 0;    // 1042
  uint32_t eph_gal = 0;    // 1046
  
  // Reference
  uint32_t ref_1005 = 0;
  uint32_t ref_1006 = 0;
  uint32_t ref_1033 = 0;
  
  uint32_t other = 0;
  uint32_t totalFrames = 0;
  uint32_t syncBytes = 0;
  uint16_t lastType = 0;
};
```

### Message Type Counter

```cpp
void countRTCM3Message(uint16_t msgType) {
  switch (msgType) {
    case 1074: rtcmStats.msm4_gps++; break;
    case 1084: rtcmStats.msm4_glo++; break;
    case 1094: rtcmStats.msm4_gal++; break;
    case 1124: rtcmStats.msm4_bds++; break;
    case 1077: rtcmStats.msm7_gps++; break;
    case 1087: rtcmStats.msm7_glo++; break;
    case 1097: rtcmStats.msm7_gal++; break;
    case 1127: rtcmStats.msm7_bds++; break;
    case 1019: rtcmStats.eph_gps++; break;
    case 1020: rtcmStats.eph_glo++; break;
    case 1042: rtcmStats.eph_bds++; break;
    case 1046: rtcmStats.eph_gal++; break;
    case 1005: rtcmStats.ref_1005++; break;
    case 1006: rtcmStats.ref_1006++; break;
    case 1033: rtcmStats.ref_1033++; break;
    default: rtcmStats.other++; break;
  }
}
```

### 30-Second Summary

```cpp
void printRTCM3Summary() {
  uint32_t msm4 = rtcmStats.msm4_gps + rtcmStats.msm4_glo +
                   rtcmStats.msm4_gal + rtcmStats.msm4_bds;
  uint32_t msm7 = rtcmStats.msm7_gps + rtcmStats.msm7_glo +
                   rtcmStats.msm7_gal + rtcmStats.msm7_bds;
  
  Serial.println("[RTCM3] === 30s Summary ===");
  Serial.printf("[RTCM3] Total frames: %lu\n", rtcmStats.totalFrames);
  Serial.printf("[RTCM3] MSM4 (PPK): GPS=%lu GLO=%lu GAL=%lu BDS=%lu\n",
                rtcmStats.msm4_gps, rtcmStats.msm4_glo,
                rtcmStats.msm4_gal, rtcmStats.msm4_bds);
  Serial.printf("[RTCM3] Eph: GPS=%lu GLO=%lu BDS=%lu GAL=%lu\n",
                rtcmStats.eph_gps, rtcmStats.eph_glo,
                rtcmStats.eph_bds, rtcmStats.eph_gal);
  Serial.printf("[RTCM3] Ref: 1005=%lu 1033=%lu\n",
                rtcmStats.ref_1005, rtcmStats.ref_1033);
  
  if (msm4 > 0 || msm7 > 0) {
    Serial.println("[RTCM3] STATUS: PPK data flowing");
  } else {
    Serial.println("[RTCM3] WARNING: No MSM! Resending CFGRTCM...");
    sendPQTM("PQTMCFGRTCM,W,7,0,-90,07,06,1,0");
  }
}
```

### Auto-Recovery

If the 30-second summary detects zero MSM messages, it automatically resends
CFGRTCM. This handles edge cases where the module loses RAM config.

### File Logging

All valid RTCM3 frames are written to `.rtcm3` regardless of message type.
No filtering needed — RTKCONV handles both MSM4 and MSM7.

---

## Commands That DO NOT Work

```
$PQTMCFGMSGRATE,W,RTCM3-1077,1       ← ERROR
$PQTMCFGMSGRATE,W,RTCM3-1077,1,0     ← ERROR
$PQTMCFGMSGRATE,R,RTCM3-1077         ← ERROR
$PQTMCFGRTCMOUTPUT,W,1               ← ERROR,3
```

`PQTMCFGMSGRATE` works for NMEA and ephemeris messages only.
MSM output is controlled exclusively by `$PQTMCFGRTCM` in base mode.

Tested on both firmware versions (AANR01A06S and AANR02A01S) — same behavior.

---

## MSM4 vs MSM7

| Aspect | MSM4 | MSM7 |
|--------|------|------|
| Pseudorange | Yes | Yes (finer resolution) |
| Carrier phase | Yes | Yes (finer resolution) |
| Doppler | No | Yes |
| CNR/SNR | No | Yes |
| RTKLIB PPK | Full support | Full support |
| PPK accuracy | Centimeter | Centimeter (marginal improvement) |
| Status | Working | Firmware outputs MSM4 despite config |

---

## PPK Pipeline

1. E1 logs `.rtcm3` to SD card during race
2. Upload to S3 via Wi-Fi at yacht club
3. RTKCONV: RTCM3 → RINEX (.obs + .nav)
4. Download CORS data from MAMI station (geodesy.noaa.gov/UFCORS)
5. RTKPOST: rover .obs + CORS .obs → centimeter positions

---

## Hardware

| Component | Detail |
|-----------|--------|
| Module | Quectel LG290P03 |
| Firmware | AANR02A01S (v2.01) |
| Board | Waveshare breakout (no RTC battery) |
| USB chip | CH343 |
| UART to ESP32 | UART3 via SH1.0 connector |
| ESP32 pins | GPIO16 (RX2) / GPIO17 (TX2) |
| Baud rate | 460800 |
| Unique ID | 000018A5DA5A8428 |

---

*Last updated: April 6, 2026*
