# SailFrames E1 — Power System Update & Battery ADC

## Date: April 6, 2026

---

## Summary

Replace the Adafruit PowerBoost 1000C with the DWEII Type-C USB 5V 2A Boost Converter
boards ($12.39/10pcs from Amazon). Update battery voltage monitoring to use GPIO34 with
a 100K/100K voltage divider connected directly to the LiPo cell.

---

## Power System Change

### Old System (Remove)
- Adafruit PowerBoost 1000C ($19.99)
- Separate charging circuit
- Enable pin for software shutdown

### New System (Install)
- DWEII Type-C USB 5V 2A Boost Converter ($1.24/unit)
- Built-in LiPo charging via USB-C
- Built-in overcharge/overdischarge protection
- LED battery level display
- Simpler, cheaper, faster charging

### Bill of Materials Update

| Component | Old | New | Price |
|-----------|-----|-----|-------|
| Boost/charger | PowerBoost 1000C | DWEII USB-C Boost | $1.24 vs $19.99 |
| LiPo cell | Adafruit 263665 3.7V | Same — no change | $38.99 |
| Voltage divider | Was on PowerBoost output | Now on LiPo B+ directly | 2x 100K resistors |

**Savings per unit:** ~$18.75
**Savings for 20 fleet units:** ~$375

---

## Wiring

### DWEII Boost Board Connections

```
LiPo Pouch Cell (3.7V 6000mAh)
  │
  ├── Red (+) ──→ Boost Board B+ pad
  ├── Black (-) ──→ Boost Board B- pad (GND)
  │
  │   Boost Board USB-C Output (5V)
  │     ├── VBUS (5V) ──→ ESP32 VIN
  │     └── GND ──→ ESP32 GND
  │
  │   Battery Voltage Monitoring (tap from LiPo B+/B-)
  │
  ├── Red (+) ──→ 100K resistor ──┬──→ GPIO34 (ADC input)
  │                                │
  │                            100K resistor
  │                                │
  └── Black (-) ──→───────────────┘──→ GND
```

### Key Points
- The voltage divider taps directly from the LiPo cell, NOT from the 5V boost output
- This reads the actual cell voltage (3.0V–4.2V range)
- The 100K/100K divider halves the voltage: ADC sees 1.5V–2.1V (within ESP32 3.3V max)
- Total current drain from divider: 0.021 mA (negligible)

---

## Firmware Changes

### Pin Definition

```cpp
// Change from whatever current pin is used to:
#define BATT_ADC_PIN  34    // GPIO34 — input only, no pullup (ideal for ADC)
```

**GPIO34 is used because:**
- It is input-only on ESP32 (no accidental output that could damage the ADC)
- It has no internal pullup/pulldown that would affect the voltage divider reading
- It is on ADC1 (ADC2 conflicts with Wi-Fi)

**GPIO35 status:**
- GPIO35 is **freed up** — no longer used for battery monitoring
- GPIO35 is also input-only and on ADC1
- Can be repurposed for a future sensor (e.g., second ADC channel, light sensor)
- If not used, leave it unconnected (floating input-only pins are safe on ESP32)

### Battery Reading Code

```cpp
#define BATT_ADC_PIN      34
#define BATT_DIVIDER_RATIO 2.0    // 100K + 100K voltage divider
#define BATT_SAMPLES       16     // average multiple readings for stability

float readBatteryVoltage() {
  uint32_t sum = 0;
  for (int i = 0; i < BATT_SAMPLES; i++) {
    sum += analogRead(BATT_ADC_PIN);
    delayMicroseconds(100);
  }
  float adcAvg = (float)sum / BATT_SAMPLES;
  
  // ESP32 ADC: 12-bit (0-4095), reference ~3.3V
  // But ESP32 ADC is nonlinear — use calibrated conversion
  float adcVoltage = adcAvg / 4095.0 * 3.3;
  
  // Multiply by divider ratio to get actual battery voltage
  float battVoltage = adcVoltage * BATT_DIVIDER_RATIO;
  
  return battVoltage;
}

int batteryPercent(float voltage) {
  // LiPo discharge curve (approximate)
  if (voltage >= 4.20) return 100;
  if (voltage >= 4.10) return 90;
  if (voltage >= 4.00) return 80;
  if (voltage >= 3.90) return 60;
  if (voltage >= 3.80) return 40;
  if (voltage >= 3.70) return 20;
  if (voltage >= 3.60) return 10;
  if (voltage >= 3.50) return 5;
  return 0;  // below 3.5V — critically low
}
```

### Battery Logging (30-second interval)

```cpp
void logBattery() {
  float voltage = readBatteryVoltage();
  int percent = batteryPercent(voltage);
  
  float adcRaw = analogRead(BATT_ADC_PIN);
  float adcVoltage = adcRaw / 4095.0 * 3.3;
  
  Serial.printf("[BATT] ADC raw=%.0f, ADC voltage=%.2fV, Battery=%.2fV (%d%%)\n",
                adcRaw, adcVoltage, voltage, percent);
}
```

---

## GPIO Pin Map (Updated)

| GPIO | Function | Direction | Notes |
|------|----------|-----------|-------|
| 2 | Onboard LED | Output | Status indicator |
| 5 | SD Card CS | Output | SPI chip select |
| 13 | Power Button | Input | Wake from deep sleep, 2s hold for shutdown |
| 16 | GPS RX (UART2 RX) | Input | LG290P TXD3 via SH1.0 |
| 17 | GPS TX (UART2 TX) | Output | LG290P RXD3 via SH1.0 |
| 18 | SD Card CLK | Output | SPI clock |
| 19 | SD Card MISO | Input | SPI data in |
| 21 | I2C SDA | Bidirectional | BNO085 + OLED (shared bus) |
| 22 | I2C SCL | Output | BNO085 + OLED (shared bus) |
| 23 | SD Card MOSI | Output | SPI data out |
| **34** | **Battery ADC** | **Input only** | **100K/100K divider from LiPo B+** |
| 35 | **Free** | Input only | Available for future use |

---

## Resistor Specification

| Parameter | Value |
|-----------|-------|
| Type | 100K ohm (100,000Ω) |
| Quantity | 2 per E1 unit |
| Package | Through-hole 1/4W (for perfboard) |
| Tolerance | 1% or 5% (either works) |
| Power rating | 1/4W (actual dissipation: 0.044mW) |

**Why 100K and not lower:**

| Resistor Value | Current Drain | Battery Impact |
|----------------|--------------|----------------|
| 100Ω | 21 mA | Kills battery in hours |
| 10K | 0.21 mA | Wastes 5mAh/day |
| 100K | 0.021 mA | Negligible (0.5mAh/day) |
| 1M | 0.002 mA | Best but ADC accuracy degrades |

100K is the sweet spot — low enough for accurate ADC readings, high enough for
negligible battery drain.

---

## Charging

The DWEII boost board charges the LiPo via its USB-C port. Connect any USB-C
charger (phone charger works). The board handles:
- CC/CV charging profile (4.2V cutoff)
- Overcharge protection
- Overdischarge protection (~3.0V cutoff)
- Short circuit protection
- LED indicator shows charge level

**Charging while running:** You can charge and operate simultaneously. The boost
converter runs from the cell while the charger tops it up. Good for bench debugging
with USB-C charger connected.

---

## Hardware Notes

- The DWEII board has solder pads for B+ and B- (battery) on one side
- The USB-C port provides both 5V output AND charging input
- There is a power button pad (K point) — can be wired to an external momentary
  switch for hard power on/off if desired
- The LED display shows approximate battery level (4 LEDs)
- Board weight: ~2g

---

## KiCad Schematic Update

Update the E1 schematic to reflect:
1. Remove PowerBoost 1000C component and connections
2. Add DWEII boost board symbol (or generic boost module)
3. Add 2x 100K resistor symbols in voltage divider configuration
4. Connect divider midpoint to GPIO34 net (label: BATT_ADC)
5. Connect divider high side to LiPo B+ net
6. Connect divider low side to GND net
7. Remove any connections to GPIO35 (mark as NC or leave unconnected)

---

*Last updated: April 6, 2026*
