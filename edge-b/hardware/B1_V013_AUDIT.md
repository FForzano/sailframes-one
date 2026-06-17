# B1 v0.13 full pin/connection/placement audit (2026-06-17)

Audited the schematic netlist (kicad-cli export, authoritative) against datasheets, plus
PCB footprint placements. **Audit target: commit `63c9836` (on-disk = committed; the notch
+ LiPo move are NOT saved yet, so their placement is NOT covered here).**

## Method note
- Connectivity from `kicad-cli sch export netlist` (loads fine).
- **CLI DRC could not run** — kicad-cli 10.0.0 rejects the PCB (format version `20260206`,
  "Failed to load board"), even on a clean copy. Clearance/courtyard DRC therefore relies on
  the **in-KiCad DRC** (user reports clean). Connectivity (the U_HALL-class checks) is fully
  CLI-verified.

## Result: NO electrical errors found. Several cosmetic notes + items to confirm.

### Power tree — ✅ all verified
- VBAT → L1(22µH) → MT3608 SW → D9(SS14) → V5_UNSW → Q_PWR1(AO3401 S→D) → V5_SW → ESP32 VIN.
- MT3608 FB divider R10/R11 = 100k/13.7k → Vout = 0.6·(1+100/13.7) = **4.98 V** ✓.
- Charge: V_QI → D8(SS14) → TP4056_VCC → TP4056 → VBAT. Option-A: TP4056_VCC → D7 → V5_SW
  (powers MCU on the pad). Diode directions all correct.
- TP4056: PROG R6=2k → ~600 mA charge; TEMP via R7 10k→GND (temp-protect disabled, charging
  enabled — v0.12 charged OK); CE tied to VCC (always on); EP→GND ✓.
- Battery monitor: R1/R2 = 100k/100k → VBAT/2 → GPIO34 (4.2 V→2.1 V, in ADC range) ✓.

### v0.13 on/off (Qi switch) — ✅ verified
- LATCH_Q (=boost EN + P-FET driver) driven by GPIO19 via R28=**0Ω** + R30 100k pulldown
  (default-off). QI_PRESENT divider R31/R32 = 47k/68k → GPIO15. (Full detail in
  `B1_V013_QI_POWER.md`.)

### U1 LC29HEAMD (24-LCC) — ✅ verified against Quectel datasheet pin table
Every pin number matches the datasheet (NO U_HALL-class number swap):
- VCC=23→V3V3, V_BCKP=22→GNSS_V_BCKP(via D10 from V3V3), GND=10/12/13/24, RESET_N=8 (R16 10k
  pull-up), 1PPS=3, TXD1=20, RXD1=21, VDD_RF=9→L2 bias-tee→ANT_FEED, RF_IN=11←C11 DC-block.
- **D_SEL1/D_SEL2 (pins 5/6) left N/C = CORRECT.** Datasheet: internal 75 kΩ pulldowns →
  default `0,0` = **UART1** (Table 8). Our symbol mislabels them "RESERVED" (cosmetic only).
- **UART 3.3 V direct (no level shifter) = matches Quectel reference design** (Fig 11, "MCU
  voltage level: 3.3 V"). Module I/O typ 2.8 V but RXD1 is 3.3 V-tolerant per the reference.
- Reserved pins 2/4/17 floating ✓ (datasheet: must float). VDD_EXT(7), ANT_ON(14),
  WAKEUP(1), TXD2/RXD2(15/16 debug), I2C(18/19) all N/C ✓ (UART1 mode).
- GNSS bias-tee: VDD_RF(PO,=VCC) → L2 33nH choke → ANT_FEED → J3 U.FL + C11 100pF DC-block →
  RF_IN ✓. C10 10nF VDD_RF decoupling ✓.

### Other ICs / connectors — ✅ verified
- TP4056 (SOIC-8-EP), MT3608 (SOT-23-6), AO3401 (G/S/D), MMBT3904 (B/E/C), SS14 (D_SMA)
  packages + pinouts all correct.
- J5 microSD: CS→pad2, MOSI→pad3, VDD→pad4, SCK→pad5, GND→pad6, MISO→pad7 ✓ (v0.13 fix).
- J8 BNO085: 3V3/GND/SCL/SDA on pins 1-4 ✓ (matches proven v0.12 + `reference_b1_bno085_pinout`).
- J9 TFT: BL/SCK/MOSI/DC/RST/CS/GND/V5_SW ✓ (5 V powered, level-shifted board, v0.12-proven).
- ESP32 socket (J1/J4): all 30 pins match firmware defines + pin map; input-only pins
  34/35/39 used only as inputs ✓.
- I2C pull-ups R21/R22 = 4.7k ✓. LEDs D1-D6 polarity + series R ✓. Decoupling on right rails ✓.

## Notes (not bugs, worth recording)
1. **Cosmetic symbol mislabels on U1**: pins 2/4/15/16/5/6 carry old BA/CA names
   (FWD/WHEELTICK/RESERVED/D_SEL) — electrically N/C-correct, but rename for clarity someday.
2. **No GNSS backup retention when off**: V_BCKP = V3V3 via D10, so it drops at power-off →
   cold start (~26 s) each boot, no hot-start. Acceptable (AGNSS/EPO mitigate). MCU can't
   cycle V_BCKP independently to recover a hung GNSS (datasheet's recommended recovery).
3. **Strapping pins on expansion header**: GPIO12 (J13.4) and GPIO15 (J13.5, now QI_PRESENT).
   Safe with J13 unpopulated; don't let anything external drive them at boot.
4. **LEDs D4/D5/D6** are high-side from V5_SW (5 V) with cathode to the ESP32 GPIO → ~3.2 V on
   the GPIO when off (within 3.6 V abs-max, v0.12-proven; a 3V3 source would be cleaner).
5. **SS14 boost rectifier (D9, 1 A)** is adequate for the ~0.5–1 A peak; fine, slightly tight
   under sustained max load. v0.12-proven.

### U_HALL-class footprint-vs-package check (the half DRC/parity can't see)
The U_HALL bug was a footprint-pad ↔ physical-package mismatch (pad N at the wrong physical
location), invisible to ERC/DRC/parity. Re-checked the **only custom IC footprint, U1**
(`B1_JLC:GPSM-SMD_24P`): extracted pad-number → XY and matched it to the datasheet top-view.
Standard LCC numbering confirmed (pad1 top-left, sequential down-left then up-right); **pad9
(VDD_RF) + pad11 (RF_IN) in the lower-left group, pad23 (VCC) / pad24 (GND) top-right — all
at datasheet positions.** Power/UART pins are also bring-up-proven (module powers + talks),
which anchors the ring. All other parts use **standard KiCad footprints** (pad N = pin N) —
no custom-footprint U_HALL risk. ✅
> Residual to fully close the RF path: confirm a v0.12 board achieved an actual **satellite
> FIX** (not just NMEA output — the module emits empty NMEA with no fix, so "alive" doesn't
> prove the antenna→RF_IN path / VDD_RF bias).

### Placement / edge-clearance — ✅ verified (independent geometry check)
CLI DRC can't load this format, so I wrote an **independent copper-to-edge clearance check**
(parse Edge.Cuts incl. arcs; tracks/vias/pads vs every edge segment). The antenna **notch**
is real and on-disk: right edge steps in to X=170, Y≈92.5–121.3, co-located with the
**copper-pour keepout** (X165–180.5, Y86–127.5) at the DevKit antenna end (J1 socket).
- **Min copper-to-edge: ~0.59 mm (via), 0.84 mm (closest pad). Zero items < 0.2 mm.**
- **No copper in/near the notch cutout** — it clips no traces/vias/pads. Confirms KiCad DRC.
- (Caught+fixed a rotation-sign bug in my own pad transform before reporting — false negatives.)
- **LiPo**: on the B-side, connector pads unmoved (J2 unchanged) — correct, no footprint move.

## Remaining gates — do NOT block this merge, but DO block ordering boards
- **JLC CPL rotations = physical polarity of every diode/LED/IC.** Netlist polarity ✓ ≠
  physical cathode ✓ (that's the CPL rotation). MUST verify every polarized part in JLC
  "Confirm Parts Placement" before fab — top cause of dead boards.
- **GNSS RF path**: ✅ **FIELD-VALIDATED 2026-06-17** on B1 hardware — open field, **40
  satellites, HDOP 0.4, EPE accuracy 1.6 m** (autonomous). Confirms the antenna→RF_IN /
  VDD_RF bias-tee + the custom 24-pin footprint work (footprint pads 9/11 positions were
  already verified in the audit; this is the empirical backstop). Fix quality reads "GPS"
  (not "SBAS") because the LC29HEA (EA variant) has no SBAS hardware — it's AA-only; the EA
  reaches sub-metre precision via RTK corrections, not SBAS.

## Bottom line
**Connectivity, U1 footprint, AND placement/edge-clearance: audited and clean.** Two pre-fab
confirmations remain (CPL rotations, GNSS fix) — neither blocks merging the design.
