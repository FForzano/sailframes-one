# B1 Auxiliary Header Spec (J10–J15)

Six male 2.54 mm pin headers on the B1 PCB for future expansion: 3× I2C taps, 1× GPIO/ADC bank, 1× UART debug, and 1× consolidated J_AUX. Defined in commits `15a4970` (J10–J14) and `2nd commit` (J15).

## Why male pin headers?

- **Female cables (Dupont, ribbon) grip pins more reliably** than the reverse — important on a moving boat
- Standard for prototyping; matches existing B1 connectors (J2 battery, J8 BNO, J9 TFT, J_QI1 Qi)
- Female sockets on PCB exposed only as recessed holes — more failure modes (debris ingress, lower retention)

Footprint for all 5: `Connector_PinHeader_2.54mm:PinHeader_1x0N_P2.54mm_Vertical`. Pin 1 is marked by the square pad on the PCB (other pads are round).

---

## J10, J11, J12 — I2C expansion (3 parallel taps)

**Purpose:** add up to 3 external I2C devices on the same bus that already serves the BNO085 IMU (J8). All three connectors share the SAME 4 nets — they're physically separate connectors for cable-routing convenience, not separate buses.

### Pin map (4-pin)

| Pin | Net | Direction | Notes |
|-----|-----|-----------|-------|
| 1 | V3V3 | Power out | 3.3 V from MT3608 boost rail via ESP32 LDO. **~500 mA shared** across all 3.3 V devices on B1 |
| 2 | GND | Reference | Tied to main GND plane |
| 3 | I2C_SDA | Bidirectional, open-drain | Shared with BNO085 socket (J8 pin 4) and ESP32 GPIO17 |
| 4 | I2C_SCL | Bidirectional, open-drain | Shared with BNO085 socket (J8 pin 5) and ESP32 GPIO16 |

### Bus characteristics

- **Pull-ups:** R21, R22 = 4.7 kΩ to V3V3 already on the B1 PCB. **Do NOT add pull-ups on external boards.** Adding more in parallel will overload the SDA/SCL drivers (effective pull-up < 1 kΩ).
- **Voltage:** 3.3 V logic only. Do **not** connect 5 V I2C devices without level shifting.
- **Speed:** Standard 100 kHz or Fast 400 kHz (set in firmware). Up to 1 MHz Fast-mode-plus if all bus devices support it and trace lengths are short.
- **Address space:** 7-bit. **BNO085 occupies 0x4A** (configurable to 0x4B via DI pin). Avoid these and the common reserved ranges (0x00–0x07, 0x78–0x7F).

### Suggested expansion sensors

| Device | Addr | Use case |
|--------|------|----------|
| TI/Bosch DPS310 | 0x77 | Pressure → altitude → weather trend (already in code path) |
| QMC5883L / LIS3MDL | 0x0D / 0x1C | External magnetometer (away from boat's ferrous mass + lead keel) |
| SH1106 / SSD1306 OLED | 0x3C | Auxiliary status display |
| AHT20 / SHT30 | 0x38 / 0x44 | Cabin humidity/temperature |
| MAX17048 | 0x36 | Fuel gauge for the LiPo (if you replace TP4056 monitoring with smarter SoC) |

### Cabling

Standard 4-conductor Dupont jumper (female-to-female or female-to-XH). For longer runs (>30 cm) twist SDA/SCL with GND and add shielding; bus rise time will degrade.

---

## J13 — GPIO / I2S expansion (5-pin)

**Purpose:** general-purpose digital/analog I/O. Three free ESP32 pins broken out for analog input or digital expansion. Can be re-purposed as a 3-output I2S audio header if you want to add an audio codec or speaker amplifier.

### Pin map (5-pin)

| Pin | Net | ESP32 pin | Capabilities | Notes |
|-----|-----|-----------|--------------|-------|
| 1 | V3V3 | — | Power out | Shared with J10–J12 |
| 2 | GND | — | Reference | |
| 3 | GPIO36 | U4 pin 2 (VP) | **ADC1_CH0, input-only** | Best for analog. Cannot drive output (no internal pull-up either) |
| 4 | GPIO12 | U4 pin 12 | Digital I/O, ADC2_CH5, TDI(JTAG) | ⚠ **Boot strapping pin** — must be LOW at boot, or VDD_SDIO flash voltage selects 1.8V and bricks SPI flash boot. Pull DOWN externally if device on this pin can leave it high during reset |
| 5 | GPIO15 | U4 pin 18 | Digital I/O, ADC2_CH3, TDO(JTAG) | ⚠ **Boot strapping pin** — controls boot debug printout. If LOW at boot, suppresses bootloader serial messages. Pull-up internally — safe to leave floating |

### Use cases

**Analog input** (preferred):
- GPIO36 only — read battery current via shunt amp, photodiode, wind direction pot, etc.
- 12-bit ADC, 0–3.3 V range, ~10 nA input impedance
- Use `analogRead(36)` in Arduino, or `adc1_get_raw(ADC1_CHANNEL_0)` in ESP-IDF

**Digital I/O:**
- GPIO12 — outputs only AFTER boot. If pulled high during boot, ESP32 fails. Use carefully.
- GPIO15 — full-featured I/O, slight bootlog suppression risk

**I2S audio (alternative use):**
- GPIO12 → BCK (bit clock, output)
- GPIO15 → WS / LRCLK (output)
- GPIO36 cannot drive I2S data; would need to remap. **NOT a complete I2S header** without sacrificing another peripheral pin. If you want full I2S, plan to add a 6th pin or steal a TFT/LED line.

### Cabling

5-conductor Dupont jumper. Polarity matters — confirm pin 1 (square pad) is the V3V3 side before plugging in 3.3 V analog/digital probes.

---

## J14 — UART debug (4-pin)

**Purpose:** access to UART0 (USB serial) via external USB-to-UART adapter (FTDI, CP2102 module, etc.), bypassing the ESP32 DevKit V1's onboard CP2102. Useful when:
- USB-C port is mechanically inaccessible (mast mount)
- You want permanent telemetry over serial to another microcontroller
- The onboard CP2102 fails or its USB-C cable falls out

### Pin map (4-pin)

| Pin | Net | ESP32 pin | Direction | Notes |
|-----|-----|-----------|-----------|-------|
| 1 | V3V3 | — | Power out | Power external UART adapter if needed (low current — most adapters are <50 mA) |
| 2 | GND | — | Reference | |
| 3 | RX0 | U4 pin 27 (GPIO3) | ESP32 RX (input) | Connect to adapter TX |
| 4 | TX0 | U4 pin 28 (GPIO1) | ESP32 TX (output) | Connect to adapter RX |

### Bus characteristics

- **Voltage:** 3.3 V logic. **Do not connect to 5 V FTDI** without a level shifter (5 V on RX0 may damage GPIO3).
- **Baud:** typically 115200 (default ESP32 bootloader/console). Firmware-configurable up to 921600.
- **Boot strapping:** GPIO1 (TX0) and GPIO3 (RX0) are also UART0 boot console — same pins used by the onboard USB-C. **Cannot use J14 simultaneously with the USB-C cable.** Pick one.

### Use cases

- **Serial console / logging** when USB unavailable
- **Permanent OTA bridge** to a companion device (e.g., a Bluetooth module)
- **Bootloader access** for flashing firmware via external programmer

### Cabling

4-conductor Dupont. Note the TX↔RX cross: PCB TX0 → adapter RX, PCB RX0 → adapter TX. Mis-wiring won't damage anything but no data will flow.

---

## J15 — J_AUX consolidated expansion (6-pin)

**Purpose:** single-cable expansion port carrying I²C bus + an interrupt line + dual-voltage power (3.3 V and 5 V) on one header. Designed for the most common B1 expansion scenarios: external I²C sensors that prefer 5 V (e.g., KY-038 sound detector), I²C sensors with a DRDY/INT signal (e.g., RM3100 magnetometer), and any future module that needs the boost rail.

### Pin map (6-pin)

| Pin | Net | Direction | Notes |
|-----|-----|-----------|-------|
| 1 | V3V3 | Power out (3.3 V) | Required for all I²C sensors and the KY-038 (operates 3.3 V or 5 V; 3.3 V keeps the digital output at 3.3 V logic level safe for ESP32 GPIO) |
| 2 | GND | Reference | Standard ground |
| 3 | I2C_SDA | Bidirectional, open-drain | Same I²C bus as J10–J12 and BNO085 (J8, address 0x4B). 4.7 kΩ pull-up already on PCB (R21). RM3100 default address 0x20–0x23 selectable → no conflict |
| 4 | I2C_SCL | Bidirectional, open-drain | Same I²C bus. 4.7 kΩ pull-up on PCB (R22) |
| 5 | AUX_INT | Input-only (GPIO36, SVP, ADC1_CH0) | Interrupt-style input for sensors that signal "data available". Use cases: KY-038 digital output (rising-edge interrupt), RM3100 DRDY, future sensor wake/IRQ. Same net also on J13 pin 3 and U4 pin 2 |
| 6 | V5_SW | Power out (5 V, switched) | From the Acxico Qi receiver / MT3608 boost output (~5.13 V validated by bench test). Available because the Qi charging path generates this rail anyway. Useful for sensors that prefer 5 V (KY-038 supports either; future sensors may require 5 V) |

### Use cases

- **KY-038 sound sensor** — wire V3V3 (or V5_SW), GND, and digital output to AUX_INT
- **PNI RM3100 magnetometer** — wire V3V3, GND, I²C, and DRDY to AUX_INT
- **External MEMS pressure sensor** (DPS310 or BMP388) — wire V3V3, GND, I²C; AUX_INT unused (or used for FIFO interrupt)
- **Future 5 V sensor module** — wire V5_SW, GND, and digital/I²C as needed
- **Smart sensor hub** module with I²C config and an INT/wake line

### Constraints

- **AUX_INT (GPIO36) is input-only.** Cannot drive output. Cannot use as I²C, SPI, or PWM master. Pure digital input or ADC.
- **V5_SW is the SWITCHED 5 V rail** — it turns off when the device powers down via the AO3401A switch. If you need always-on 5 V, would need to tap V5_UNSW instead (not recommended for cable headers — battery drain).
- **Pin 1 V3V3 and Pin 6 V5_SW shared rail capacity** — total current across all expansion devices should stay under ~500 mA for V3V3 and ~1 A for V5_SW (limited by MT3608 boost output).

### Cabling

6-conductor cable (Dupont, JST-SH 1.0 mm with adapter, or custom ribbon). Pin 1 (square pad on PCB) is V3V3. Note the mixed-voltage layout: pin 1 is 3.3 V and pin 6 is 5 V — wire colors should differentiate to avoid plugging in backward.

---

## Mechanical / placement notes

All 5 connectors should be placed along the **top or right edge** of the PCB so cables exit through a single port hole / gland in the enclosure side wall. Cable length budget inside the Polycase: ~30 mm before reaching the wall.

Recommended placement (canvas, PCB v0.12):
- **J10, J11, J12** stacked vertically along the top-right edge, near J8 BNO socket → minimum I2C trace length
- **J13** below the I2C stack — keeps GPIO36 ADC trace short to ESP32 pin 2
- **J14** at the top-left or wherever convenient — UART traces are short by default

## Firmware notes (for future implementation)

- I2C bus init in firmware sets the BNO085 address by default; new devices need their addresses added to the scan list in `init_i2c_devices()`
- GPIO36 ADC requires calibration with `adc_set_attenuation()` for full 0–3.3 V range
- UART0 RX0/TX0 firmware lock: if user plugs in USB-C while J14 is also wired up, there will be bus contention. The firmware should detect USB CDC connection state and disable UART0 forwarding while USB is active.

## Test plan (when populating these headers)

1. Multimeter check: probe J10 pin 1 to GND — expect 3.3 V (within ±5%)
2. Continuity: probe J10 SDA to J11 SDA to J12 SDA — should all be the same net (zero ohms)
3. I2C device scan: `i2cdetect -y 0` should show 0x4A (BNO085) and any new devices
4. GPIO36 read: short to GND and read 0; short to 3.3 V via 10 kΩ → read ~4095
5. UART loopback: jumper RX0↔TX0 on J14 → send bytes, expect echo

---

*Generated 2026-05-20 by Claude as part of B1 schematic commit `15a4970`.*
