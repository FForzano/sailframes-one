# B1 Pin Map & Net Reference

Single source of truth for schematic capture. Derived from spec v0.10 sections 3–11.
Net names in **bold** are the suggested KiCad net labels for cross-sheet connectivity.

---

## Power Rails

| Net | Source | Loads | Notes |
|---|---|---|---|
| **VBAT** | LiPo + (via JST PH J2) | TP4056 BAT pin, MT3608 VIN, battery monitor divider, Hall sensor U_HALL, FF U_FF, supervisor U_RST | 3.0–4.2 V from protected cell |
| **V5_UNSW** | TP4056 + Qi + USB-C (OR-ed via D7/D8 SS14) | MT3608 input only | Not connected to ESP32 — gated by latch |
| **V5_SW** | MT3608 VOUT (gated by 74LVC1G74 Q via Q_PWR P-MOSFET) | ESP32 VIN, TFT VCC | 5 V switched rail, OFF when latch unset |
| **V3V3** | ESP32 DevKit V1 3V3 pin (AMS1117 onboard) | LC29HEAMD VCC, BNO085 VIN, I2C pull-ups, RESET_N pull-up, microSD VCC, LED pull-ups | 3.3 V from DevKit's onboard regulator |
| **GND** | LiPo − / global | All | Pour both layers, via-stitch under RF |

---

## ESP32 DevKit V1 GPIO Map

Pin-compatible with E1 v1.1 firmware. All 5 net labels in column 3 should match across sheets.

| ESP32 Pin | Function | Net Label | Destination |
|---|---|---|---|
| GPIO16 (U2RX) | GNSS UART RX | **GNSS_TXD** | LC29HEAMD TXD1 |
| GPIO17 (U2TX) | GNSS UART TX | **GNSS_RXD** | LC29HEAMD RXD1 |
| GPIO39 (input only) | 1 PPS from GNSS | **GNSS_1PPS** | LC29HEAMD 1PPS output |
| GPIO21 | I²C SDA | **I2C_SDA** | BNO085 SDA (with 4.7 KΩ pull-up to V3V3) |
| GPIO22 | I²C SCL | **I2C_SCL** | BNO085 SCL (with 4.7 KΩ pull-up to V3V3) |
| GPIO5 | TFT chip select | **TFT_CS** | TFT CS |
| GPIO4 | TFT reset | **TFT_RST** | TFT RESET |
| GPIO2 | TFT data/cmd | **TFT_DC** | TFT DC/RS |
| GPIO23 | VSPI MOSI | **VSPI_MOSI** | TFT SDI |
| GPIO18 | VSPI SCK | **VSPI_SCK** | TFT SCK |
| GPIO25 | TFT backlight PWM | **TFT_BL** | TFT LED (via ~22 Ω series R) |
| — | TFT SDO | N/C | TFT MISO unused — leave N/C |
| GPIO14 | HSPI CLK | **HSPI_SCK** | microSD CLK |
| GPIO13 | HSPI MOSI | **HSPI_MOSI** | microSD MOSI |
| GPIO35 (input only) | HSPI MISO | **HSPI_MISO** | microSD MISO |
| GPIO27 | HSPI CS | **HSPI_CS** | microSD CS |
| GPIO34 (input only, ADC1_6) | Battery voltage | **VBAT_DIV** | Mid-point of 100 K / 100 K divider on VBAT |
| GPIO33 | D4 Red LED (heartbeat) | **LED_HB_N** | D4 anode-side, active LOW via 220 Ω |
| GPIO32 | D5 White LED (GPS fix) | **LED_GPS_N** | D5 active LOW via 220 Ω |
| GPIO26 | D6 Cyan LED (SD activity) | **LED_SD_N** | D6 active LOW via 220 Ω |
| GPIO19 | Hall latch readback | **LATCH_Q_RB** | 74LVC1G74 Q via 10 KΩ + 3.3 V clamp (or 10 K/22 K divider) |
| GPIO36 (input only, ADC1_0) | RESERVED | — | Future use |
| GPIO15 | RESERVED (strap) | — | Avoid input drive at boot |
| GPIO0 | RESERVED (boot strap) | — | DevKit handles |
| GPIO12 | RESERVED (strap MTDI) | — | Do not use — boot fails if HIGH at boot |
| VIN | 5 V input | **V5_SW** | From Q_PWR MOSFET drain (Hall-latch-gated) |
| 3V3 (output) | Regulator output | **V3V3** | Rail to all 3.3 V loads |
| GND | Ground | **GND** | Multiple pins, all to GND pour |

---

## LC29HEAMD (U1) — JLCPCB Extended part, footprint from JLC2KiCadLib (B1_JLC)

| LC29HEAMD Pin | Net | Notes |
|---|---|---|
| VCC | V3V3 | 10 µF + 100 nF + 10 nF decoupling within 5 mm |
| V_BCKP | V3V3 (via SS14 D10) | Backup supply through Schottky diode |
| GND (multiple) | GND | All GND pins to pour |
| RESET_N | (pulled to V3V3 via 10 KΩ) + TP3 | Optional ESP32 GPIO control — TBD in firmware |
| ON_OFF | V3V3 (via 10 KΩ pull-up) | Continuous-on mode |
| D_SEL1, D_SEL2 | GND (via 10 KΩ pull-down each) | UART1 default mode. **DO NOT tie to V3V3 — 1.8 V tolerant only.** |
| TXD1 | GNSS_TXD → GPIO16 | + TP1 |
| RXD1 | GNSS_RXD ← GPIO17 | + TP2 |
| TXD2, RXD2 | N/C | UART2 is 1.8 V, no level shifter |
| 1PPS | GNSS_1PPS → GPIO39 | Input-only ESP32 pin, no strapping risk |
| EXT_INT, WI, RESERVED | N/C | Per datasheet |
| VDD_RF | RF bias-T input | Via L_BIAS 33 nH → u.FL J3 center |
| RF_IN | RF input | Via C_BLOCK 100 pF ← u.FL J3 center |

**Bias-T network at u.FL J3:**
```
VDD_RF ──[L_BIAS 33 nH]──┬── J3 center pin
                          ├──[C_BYPASS 10 nF]── GND
RF_IN  ──[C_BLOCK 100 pF]─┘
```

---

## BNO085 IMU Socket (J8, optional populate)

9-pin female header matching Adafruit BNO085 STEMMA QT breakout.

| Pin | Net |
|---|---|
| VIN | V3V3 |
| GND | GND |
| 3Vo | N/C (breakout's regulated output) |
| SDA | I2C_SDA |
| SCL | I2C_SCL |
| INT | N/C (or future GPIO if firmware uses interrupts) |
| RST | N/C (or future GPIO if firmware controls reset) |
| P0, P1 | per breakout defaults — I²C @ 0x4A |

**Pull-ups on B1 PCB** (not relying on breakout): 4.7 KΩ from SDA→V3V3 and SCL→V3V3.

---

## TFT Display Socket (J9/J10, optional populate)

2× 8-pin female header pair matching Hosyond 3.5″ ST7796U pinout.

| TFT Pin | Net |
|---|---|
| VCC | V5_SW |
| GND | GND |
| CS | TFT_CS |
| RESET | TFT_RST |
| DC/RS | TFT_DC |
| SDI/MOSI | VSPI_MOSI |
| SCK | VSPI_SCK |
| LED (backlight) | TFT_BL (via ~22 Ω) |
| SDO/MISO | **N/C** |
| T_CLK, T_CS, T_DIN, T_DO, T_IRQ | N/C (touch unused) |
| SD_MOSI, SD_MISO, SD_SCK, SD_CS | N/C (TFT's built-in SD slot unused; B1 has its own microSD) |

---

## microSD Socket (J5, SMD push-push, always-populated)

| microSD Pin | Net | Pull-up |
|---|---|---|
| CLK | HSPI_SCK | 10 KΩ to V3V3 |
| MOSI | HSPI_MOSI | 10 KΩ to V3V3 |
| MISO | HSPI_MISO | 10 KΩ to V3V3 |
| CS | HSPI_CS | 10 KΩ to V3V3 |
| VCC | V3V3 | 10 µF + 100 nF decoupling |
| GND | GND | — |
| CD (card detect) | optional ESP32 GPIO | 10 KΩ to V3V3 |

3.3 V signalling, no level shifter (microSD spec is 2.7–3.6 V).

---

## Hardware Power Switch (Section 10) — Magnetic Toggle Latch

Authoritative pin map for the JLC2KiCadLib-imported parts, verified against TI/Maxim datasheets:

**U_HALL (DRV5032AJ, X2SON-4):**
| Pin | Function | Net |
|---|---|---|
| 1 | VCC | VBAT |
| 2 | OUT (active LOW, open-drain) | **HALL_OUT** |
| 3 | GND | GND |
| 4 | EP (exposed pad) | GND |

(VDD pull-up: HALL_OUT → 100 KΩ → VBAT to satisfy open-drain output.)

**U_FF (SN74LVC1G74DCTR, SM8 — authoritative pin map, differs from spec line 1057–1077 prose; see spec checklist line 1267):**
| Pin | Function | Net |
|---|---|---|
| 1 | CLK | **CLK_DEBOUNCED** (HALL_OUT via 10 KΩ + 100 nF debounce to GND) |
| 2 | D | tied to /Q (pin 3) for toggle config |
| 3 | /Q | tied to pin 2 D |
| 4 | GND | GND |
| 5 | Q | **LATCH_Q** → 2N3904 base + MT3608 EN + GPIO19 (via 10 KΩ + clamp) |
| 6 | /CLR | from U_RST /RESET (push-pull active-LOW) |
| 7 | /PRE | VBAT (tied high — never preset) |
| 8 | VCC | VBAT |

**U_RST (MAX809T, SOT-23-3, 3.08 V threshold, 240 ms timeout):**
| Pin | Function | Net |
|---|---|---|
| 1 | GND | GND |
| 2 | RESET (active-LOW push-pull) | → U_FF /CLR |
| 3 | VDD | VBAT |

**Q_INV (2N3904 NPN level shifter):**
- Base: LATCH_Q via R_BASE 10 KΩ
- Emitter: GND
- Collector: → Q_PWR gate, plus R_PULLUP 100 KΩ to V5_UNSW

**Q_PWR (AO3401A P-MOSFET):**
- Source: V5_UNSW (MT3608 VOUT)
- Drain: V5_SW (to ESP32 VIN, TFT VCC)
- Gate: from 2N3904 collector + R_PULLUP

**MT3608 (U3, SOT-23-6):**
- VIN: VBAT
- EN: LATCH_Q (double-gating with Q_PWR — kills 1.9 mA quiescent when latch is OFF)
- SW: switch node to L1 (22 µH)
- FB: divider to set V5_UNSW = 5.0 V (R_FB1 100 KΩ top, R_FB2 32.4 KΩ bottom typical)
- GND: GND

---

## Status LEDs (D1–D6, bottom edge of PCB, 15 mm spacing)

| Ref | Color | Driven by | Net | Series R |
|---|---|---|---|---|
| D1 | Blue | Qi receiver 5 V (present detector) | **V_QI** via 470 Ω | 470 Ω |
| D2 | Yellow | TP4056 CHRG (open-drain, active LOW when charging) | TP4056 CHRG pin via 1 KΩ to V5_UNSW | 1 KΩ |
| D3 | Green | TP4056 STDBY (open-drain, active LOW when full) | TP4056 STDBY pin via 1 KΩ to V5_UNSW | 1 KΩ |
| D4 | Red | ESP32 GPIO33 (active LOW) | LED_HB_N | 220 Ω |
| D5 | White | ESP32 GPIO32 (active LOW) | LED_GPS_N | 220 Ω |
| D6 | Cyan | ESP32 GPIO26 (active LOW) | LED_SD_N | 220 Ω |

---

## Test Pads (TP1–TP4, exposed copper, top layer, no through-hole)

| TP | Net | Use |
|---|---|---|
| TP1 | GNSS_TXD | LC29HEA UART1 TXD direct access for QGPSFlashTool |
| TP2 | GNSS_RXD | LC29HEA UART1 RXD direct access |
| TP3 | LC29HEA RESET_N | Pull LOW to force bootloader |
| TP4 | GND | Probe reference |

---

## ERC sanity rules (apply during capture)

1. Every **V3V3** load has decoupling within 5 mm.
2. **GND** is one global net; no isolated grounds.
3. **VSPI** (TFT) and **HSPI** (microSD) are *separate buses* — verify net labels never cross.
4. **GNSS_TXD / GNSS_RXD** are the ESP32-side perspective: GNSS_TXD = data flowing FROM LC29HEAMD TO ESP32 (GPIO16 RX).
5. **V5_SW** never drives directly off MT3608 — must pass through Q_PWR P-MOSFET (Hall-latch double-gating).
6. **MT3608 EN** must net to LATCH_Q, not to VBAT or V5_UNSW. (Spec checklist line 1259 — canary for the "1.9 mA quiescent" bug.)
7. **U_RST** is on U_FF /CLR — no RC POR network. (Spec checklist line 1260.)
8. **L_BIAS = 33 nH**, not 10 nH. (Spec checklist line 1261.)
9. **TFT_BL = GPIO25**, not GPIO19. GPIO19 is reserved for LATCH_Q_RB. (Spec checklist line 1262.)
10. **D_SEL1, D_SEL2 to GND** — never to V3V3. (Spec checklist line 1255.)
