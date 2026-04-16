# SailFrames Ultrasonic Wind Sensor — Development Spec

## Overview

Open-source ultrasonic anemometer co-processor for the SailFrames E1 fleet tracker. Based on the QingStation design by majianjia, adapted for marine use in Boston Harbor. The wind sensor uses an STM32L476 co-processor that communicates with the E1's ESP32 over UART2 (GPIO32/GPIO33).

**Design reference:** github.com/majianjia/QingStation (anemometer.md is the primary reference)
**Additional references:** soldernerd.com/arduino-ultrasonic-anemometer, dl1glh.de/ultrasonic-anemometer

---

## Hardware — Current State

### Co-processor
- **MCU:** STM32L476RG on NUCLEO-L476RG dev board (same as QingStation)
- **Clock:** 80MHz from HSI + PLL
- **IDE:** STM32CubeIDE 2.1.1 + STM32CubeMX on macOS
- **Project:** `blinkMX` in `hardware/blinkMX/` (this repo)

### Transducers
- **Prototype (bench):** HiLetgo TCT40-16R/T, 16mm, 40kHz, open-end, non-waterproof (20pcs on hand)
- **Final (marine):** Same Sky CUSA-TR60-02-2000-TH67, 10mm, 40kHz, IP67, aluminum, transceiver (8pcs on order from DigiKey)
- **Beam angle:** 60° typical at -6dB (Same Sky spec)
- **Impedance:** 3,000Ω max
- **Capacitance:** 1,600–2,400pF

### Analog Front-End (not yet wired)
- **Driver:** MAX3232 DIP-16 breakout modules (10pcs on hand) — generates ~10Vpp from 3.3V supply via charge pump
- **Amplifier:** LM358 DIP-8 dual op-amp (50pcs on hand) — 1MHz GBP, ~25× max gain at 40kHz
- **Analog mux:** CD4052BE DIP-16 dual 4:1 multiplexer (6pcs on order from DigiKey)
- **Protection:** 1N4148 signal diodes (125pcs on hand)

### Test Equipment
- **Oscilloscope:** Siglent SDS1104X-E, 4-channel, 100MHz, accessible via Ethernet at 10.10.4.2:5025 (SCPI)
- **Scope screenshot script:** `scope_screenshot_png.py` — captures PNG over network

---

## Firmware — Current State

### Working
- [x] LED blink on PA5 (LD2)
- [x] UART serial output on USART2 at 115200 baud ("Hello from Nucleo")
- [x] 40kHz PWM output on PA0 (TIM2_CH1, prescaler=0, period=1999, pulse=1000)
- [x] ADC1 reading on PB0/A3 (channel IN15, 12-bit, synchronous clock div4)
- [x] ADC calibration with `HAL_ADCEx_Calibration_Start()`
- [x] Verified 40kHz square wave at 1.65V DC average on multimeter
- [x] Verified ADC responds: 0V→0, 3.3V→4095, floating→random
- [x] Ultrasonic coupling confirmed: ~800mV p-p sine wave received at 5cm without amplifier
- [x] Oscilloscope screenshot capture via Python/SCPI over Ethernet

### Pin Assignments
| Pin | Function | Arduino Label | Notes |
|-----|----------|---------------|-------|
| PA0 | TIM2_CH1 PWM 40kHz | A0 | Transmitter drive |
| PA1 | (available) | A1 | ADC1_IN6 — tested, had issues |
| PA2 | USART2_TX | — | Serial to Mac |
| PA3 | USART2_RX | — | Serial from Mac |
| PA4 | (available) | A2 | ADC1_IN9 — tested, had issues |
| PA5 | LD2 LED | — | Onboard green LED |
| PB0 | ADC1_IN15 | A3 | Receiver ADC input (working) |
| PC13 | B1 button | — | User button (active low) |

### ADC Notes
- PA1 (IN6) and PA4 (IN9) did not respond to external voltage — cause unknown, possibly solder bridge or pin conflict
- PB0 (IN15) works correctly with stop/start per conversion cycle
- Must use `HAL_ADC_Start()` → `HAL_ADC_PollForConversion()` → `HAL_ADC_GetValue()` → `HAL_ADC_Stop()` pattern
- Clock prescaler must be **Synchronous clock mode divided by 4** (async mode failed)
- Calibration required before first use: `HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED)`

---

## Next Steps — Development Roadmap

### Phase 1: Burst Mode (COMPLETE ✓)
Send a burst of pulses at 40kHz instead of continuous PWM, then listen for the echo on the ADC.

**Tasks:**
- [x] Configure TIM2 to generate a counted burst (software start/stop with DWT microsecond timing)
- [x] Set up fast ADC capture using direct register access
- [x] Dump raw ADC samples over UART to Mac for plotting in Python/matplotlib
- [x] Identify the echo pulse in the captured data and measure its arrival time
- [x] Verify echo timing changes with transducer distance

**Results (April 15, 2026):**
| Distance | Echo Start | Peak | Vpp |
|----------|-----------|------|-----|
| 5cm | 436µs | 724µs | 312mV |
| 10cm | ~600µs | 1196µs | 181mV |

**Implementation notes:**
- Burst: 8 pulses @ 40kHz (200µs burst duration)
- Pre-capture delay: 50µs for transducer ringdown
- ADC sample rate: ~160kHz (measured, slower than theoretical due to register polling overhead)
- Capture window: 1000 samples ≈ 6.25ms
- Receiver bias: 10kΩ/10kΩ voltage divider to 1.65V (centers signal at ADC mid-scale)
- Python plotting: `scripts/plot_adc.py` with auto echo detection

### Phase 2: Single-Channel Time-of-Flight
Measure the time between pulse transmission and echo reception on one transducer pair.

**Tasks:**
- [ ] Implement peak detection in firmware
- [ ] Implement zero-crossing interpolation for sub-sample accuracy
- [ ] Calculate time-of-flight and display over serial
- [ ] Verify time changes with distance

### Phase 3: MAX3232 Driver Integration
Add the RS-232 level driver for stronger transducer excitation (~10Vpp vs 3.3Vpp).

**Tasks:**
- [ ] Wire MAX3232 module between TIM2 output and transmitter transducer
- [ ] Compare signal strength with and without driver on oscilloscope
- [ ] Evaluate if MAX3232 is even needed (current direct-drive produces 800mV p-p at receiver)
- [ ] If used, implement shutdown control to eliminate charge pump noise during receive

### Phase 4: LM358 Amplifier
Add receive amplifier if signal is too weak for reliable detection.

**Tasks:**
- [ ] Design two-stage amplifier (QingStation schematic as reference)
- [ ] Wire on breadboard, verify gain and bandwidth on oscilloscope
- [ ] Tune gain — may need less than QingStation's design given strong transducer signal
- [ ] Add 100nF DC blocking capacitor and 4.7kΩ input resistor

### Phase 5: CD4052 Mux — 4-Channel Switching
Add analog multiplexer to switch between 4 transducer channels.

**Tasks:**
- [ ] Wire CD4052 with 4 transducers
- [ ] Control A/B select pins from STM32 GPIO
- [ ] Implement sequential measurement: N→S, S→N, E→W, W→E
- [ ] Verify all 4 channels produce consistent echoes

### Phase 6: Wind Speed Calculation
Implement the QingStation math for wind speed and direction.

**Equations (from QingStation/Hardy Lau):**
```c
alpha = atan(2*H/D);
// Wind speed per axis
ns_v = H / (sin(alpha) * cos(alpha)) * (1.0f/dt[NORTH] - 1.0f/dt[SOUTH]);
ew_v = H / (sin(alpha) * cos(alpha)) * (1.0f/dt[EAST] - 1.0f/dt[WEST]);
// Total wind speed
v = sqrtf(ns_v*ns_v + ew_v*ew_v);
// Wind direction
course = atan2f(-ew_v, -ns_v) / 3.1415926 * 180 + 180;
// Sound speed (independent temperature check)
c = H / sin(alpha) * (1.0f/dt[NORTH] + 1.0f/dt[SOUTH]);
```

**Tasks:**
- [ ] Implement wind speed calculation
- [ ] Implement fault detection (MSE peak matching, sound speed safeguard)
- [ ] Calibrate with known zero-wind condition
- [ ] Test on car roof (QingStation method)

### Phase 7: ESP32 Integration
Connect to E1 fleet tracker over UART.

**Tasks:**
- [ ] Define serial protocol: `$SFWND,speed,direction,soundspeed,status*checksum\r\n`
- [ ] Implement UART output on STM32 (TX only needed)
- [ ] Add UART2 receive handler on ESP32 (GPIO32 RX, GPIO33 TX)
- [ ] Parse wind data in E1 firmware alongside GNSS and IMU data
- [ ] Log wind data to SD card in E1 recording format

### Phase 8: 3D-Printed Marine Housing
Design and print the anemometer enclosure.

**Tasks:**
- [ ] Design reflector plate geometry in Fusion 360 (based on QingStation CFD analysis)
- [ ] Design transducer mounting with silicone sealing
- [ ] Print in ASA-CF on Bambu Lab P1S (or P2S)
- [ ] Airflow simulation if possible (Simscale free tier)
- [ ] Rain/spray testing before deployment

### Phase 9: Custom PCB
Design the co-processor PCB for fleet production.

**Tasks:**
- [ ] KiCad schematic: STM32L476 (or STM32G0) + MAX3222 + LMV358 + 74HC4052 + passives
- [ ] PCB layout optimized for JLCPCB assembly
- [ ] 4-pin UART header for ESP32 connection
- [ ] Transducer connection pads/headers
- [ ] Order from JLCPCB with SMD assembly

---

## Mechanical Parameters

Based on QingStation with Same Sky 10mm transducers:

| Parameter | Value | Notes |
|-----------|-------|-------|
| Height (H) | ~5cm | Transducer face to reflector plate |
| Pitch (D) | ~4cm | Distance between opposite transducer centers |
| Sound path | ~10.7cm | sqrt((D/2)² + H²) × 2 |
| Echo arrival | ~318µs | At 336 m/s sound speed, calm air |
| Transducer diameter | 10mm | Same Sky CUSA-TR60 |
| Housing material | ASA-CF | UV/weather resistant, printed on P1S |

---

## Signal Processing Summary (from QingStation)

1. **ADC sampling:** 1MHz, 12-bit, 1000 samples per burst, DMA-driven
2. **Preprocessing:** Subtract DC offset, bandpass filter around 40kHz, normalize
3. **Peak matching:** Locate echo beam by MSE comparison with reference calibration (±4 peaks around maximum)
4. **Zero-crossing interpolation:** 6 zero-crossings averaged for sub-sample timing (~33ns resolution)
5. **Fault detection:** MSE threshold + sound speed safeguard (±5 m/s from temperature estimate)
6. **Measurement rate:** ~44ms per full 4-channel measurement (25ms sampling + 19ms processing)

---

## Key Learnings So Far

- **Direct 3.3V PWM drive produces surprisingly strong signal** (~800mV p-p at 5cm) with Same Sky IP67 transducers — MAX3232 driver may be optional
- **STM32L476 ADC requires calibration** before first use (`HAL_ADCEx_Calibration_Start`)
- **ADC clock must be synchronous** (divided from AHB) — asynchronous mode did not work
- **Not all ADC channels work** on Nucleo board — PA1/IN6 and PA4/IN9 did not respond; PB0/IN15 works
- **ADC needs stop/start cycle** for each conversion to get fresh values
- **Siglent SDS1104X-E** is fully scriptable via Python/SCPI over Ethernet (port 5025)
- **Scope probes:** set to 1X for small transducer signals; match probe attenuation setting in scope channel menu
- **Receiver needs DC bias** — 10kΩ/10kΩ divider to 1.65V prevents signal drift and centers at ADC mid-scale
- **Direct register ADC polling is ~160kHz** — much slower than theoretical 1.3MHz due to EOC flag checking overhead; DMA needed for faster rates
- **8 pulses give 34% stronger signal than 4** — more burst energy improves SNR at distance
- **HiLetgo TCT40-16R/T are split TX/RX** — use "T" for transmitter, "R" for receiver; they're optimized differently

---

## Repository Structure

```
sailframes/wind_sensor/
├── hardware/
│   ├── blinkMX/              # STM32CubeIDE project (burst mode firmware)
│   ├── kicad/                # PCB design files (future)
│   └── 3d-print/             # Fusion 360 / STL files for housing (future)
├── scripts/
│   ├── scope_screenshot.py   # Oscilloscope capture (future)
│   ├── plot_adc.py           # ADC data visualization
│   └── wind_calc.py          # Wind speed calculation verification (future)
├── WIND_SENSOR_DEV.md        # This file
└── README.md                 # (future)
```

---

## Bill of Materials

### On Hand
| Item | Qty | Source | Status |
|------|-----|--------|--------|
| NUCLEO-L476RG | 1 | Amazon | ✅ Delivered |
| HiLetgo TCT40-16R/T 16mm transducers | 20 | Amazon | ✅ Delivered |
| MAX3232 DIP-16 modules | 10 | Amazon | ✅ Delivered |
| LM358 DIP-8 op-amps | 50 | Amazon | ✅ Delivered |
| 1N4148 diodes | 125 | Amazon | ✅ Delivered |
| Siglent SDS1104X-E oscilloscope | 1 | Micro Center | ✅ Purchased |

### On Order
| Item | Qty | Source | Status |
|------|-----|--------|--------|
| Same Sky CUSA-TR60-02-2000-TH67 | 8 | DigiKey | ⬜ Ordered |
| CD4052BE DIP-16 | 6 | DigiKey | ⬜ Ordered |

### E1 PCB Addition
| Item | Notes |
|------|-------|
| 4-pin header (2.54mm) | 3.3V, GND, GPIO32 (UART2 RX), GPIO33 (UART2 TX) |
