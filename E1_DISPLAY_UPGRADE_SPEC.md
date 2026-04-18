# E1 Firmware Update: Hosyond 3.5" IPS ST7796 Display Integration

## Overview

Replace the SSD1309 2.42" OLED (I2C, 128×64 monochrome) with the **Hosyond 3.5" IPS ST7796U** (SPI, 480×320 color) on the E1 fleet tracker. This also consolidates the standalone SD card module into the display's built-in SD slot.

**Why:** The SSD1309 OLED is unreadable through polarized sunglasses. The IPS TFT works with polarized lenses, has better viewing angles for a heeling sailboat, and the larger 480×320 color screen enables a richer dashboard.

---

## Hardware

### Display Module

- **Model:** Hosyond 3.5" 320×480 IPS Capacitive Touch Screen LCD
- **Driver IC:** ST7796U
- **Touch IC:** FT6336U (I2C capacitive touch)
- **Interface:** SPI (4-wire) for LCD, I2C for touch
- **Resolution:** 480×320
- **Panel type:** IPS (wide viewing angles — critical for heeling boat)
- **Backlight:** 6 white LEDs, 95mA, 0.5W total
- **Built-in SD card slot:** micro TF, SPI interface with separate CS
- **PCB dimensions:** 55.5 × 98 mm (fits YETLEBOX 125×75mm usable space)

### Pin Labels on Module (top to bottom)

```
SD_CS      — SD card chip select
CTP_INT    — Capacitive touch interrupt
CTP_SDA    — Capacitive touch I2C data
CTP_RST    — Capacitive touch reset
CTP_SCL    — Capacitive touch I2C clock
SDO(MISO)  — SPI data out (display + SD shared)
LED        — Backlight control
SCK        — SPI clock (display + SD shared)
SDI(MOSI)  — SPI data in (display + SD shared)
LCD_RS     — LCD data/command (DC)
LCD_RST    — LCD reset
LCD_CS     — LCD chip select
GND        — Ground
VCC        — Power (3.3V)
```

---

## Wiring: Display → ESP32

### SPI Bus (shared LCD + SD)

| Display Pin | ESP32 GPIO | Function |
|---|---|---|
| SDI(MOSI) | GPIO 23 | SPI MOSI |
| SDO(MISO) | GPIO 19 | SPI MISO |
| SCK | GPIO 18 | SPI Clock |
| LCD_CS | GPIO 5 | LCD chip select |
| SD_CS | GPIO 15 | SD card chip select |
| LCD_RS | GPIO 2 | Data/Command (DC) |
| LCD_RST | GPIO 4 | LCD reset |
| LED | GPIO 25 | Backlight (PWM for dimming) |

### Touch (I2C — shared bus with BNO085)

| Display Pin | ESP32 GPIO | Function |
|---|---|---|
| CTP_SDA | GPIO 21 | I2C SDA (shared with BNO085 @ 0x4A) |
| CTP_SCL | GPIO 22 | I2C SCL (shared with BNO085 @ 0x4A) |
| CTP_RST | GPIO 27 | Touch reset |
| CTP_INT | GPIO 26 | Touch interrupt |

**Note:** Touch is not needed for E1 sailing use. CTP pins can be left unconnected to save GPIOs. If wired, the FT6336U touch controller is likely at I2C address 0x38 — no conflict with BNO085 at 0x4A.

### Power

| Display Pin | ESP32 | Notes |
|---|---|---|
| VCC | 3.3V | ST7796U runs at 3.3V logic |
| GND | GND | |

---

## Complete E1 GPIO Map (Updated)

| GPIO | Function | Bus | Notes |
|---|---|---|---|
| 2 | LCD_RS (DC) | SPI | Data/Command select |
| 4 | LCD_RST | SPI | Display reset |
| 5 | LCD_CS | SPI | Display chip select |
| 13 | Power button | Digital | Internal pullup, ext0 deep sleep wake |
| 15 | SD_CS | SPI | SD card chip select (on display board) |
| 16 | GPS UART RX | UART2 | ESP32 RX ← LG290P TXD3 |
| 17 | GPS UART TX | UART2 | ESP32 TX → LG290P RXD3 |
| 18 | SPI CLK | SPI | Shared: LCD + SD |
| 19 | SPI MISO | SPI | Shared: LCD + SD |
| 21 | I2C SDA | I2C | BNO085 (0x4A) + optional touch (0x38) |
| 22 | I2C SCL | I2C | BNO085 (0x4A) + optional touch (0x38) |
| 23 | SPI MOSI | SPI | Shared: LCD + SD |
| 25 | LED backlight | PWM | Backlight brightness control |
| 26 | CTP_INT | Digital | Optional — touch interrupt |
| 27 | CTP_RST | Digital | Optional — touch reset |

**Freed GPIO:** The old OLED was on I2C (GPIO 21/22 shared). The old standalone SD module CS was on GPIO 5. Both GPIO 5 and the I2C bus are reused, so no GPIOs are lost.

---

## Library Changes

### Remove

- `Adafruit_SSD1306` library
- `Adafruit_GFX` library (TFT_eSPI has its own graphics)

### Add

- `TFT_eSPI` library by Bodmer (install via Arduino Library Manager)

### TFT_eSPI Configuration (`User_Setup.h`)

Create or edit the `User_Setup.h` file in the TFT_eSPI library folder:

```cpp
// ============================================================
// SailFrames E1 — TFT_eSPI User_Setup.h
// Hosyond 3.5" IPS ST7796U, 480x320, SPI
// ============================================================

#define ST7796_DRIVER

#define TFT_WIDTH  320
#define TFT_HEIGHT 480

// ESP32 SPI pin assignments
#define TFT_MOSI  23
#define TFT_MISO  19
#define TFT_SCLK  18
#define TFT_CS     5
#define TFT_DC     2
#define TFT_RST    4

// Backlight pin (optional — can also tie LED to 3.3V)
#define TFT_BL    25
#define TFT_BACKLIGHT_ON HIGH

// SPI frequency — 40MHz is safe for ST7796, try 80MHz if stable
#define SPI_FREQUENCY       40000000
#define SPI_READ_FREQUENCY  20000000
#define SPI_TOUCH_FREQUENCY  2500000

// Fonts — load only what's needed to save flash
#define LOAD_GLCD    // 8px font
#define LOAD_FONT2   // 16px font
#define LOAD_FONT4   // 26px font
#define LOAD_FONT6   // 48px numeric font (good for speed display)
#define LOAD_FONT7   // 48px 7-segment font (good for speed display)
#define LOAD_FONT8   // 75px numeric font
#define LOAD_GFXFF   // FreeFonts support
#define SMOOTH_FONT
```

---

## Firmware Changes

### 1. Replace Display Includes and Init

**Before (SSD1309 OLED):**
```cpp
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

void initDisplay() {
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 failed");
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
}
```

**After (ST7796 TFT):**
```cpp
#include <TFT_eSPI.h>
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();

// Backlight
#define TFT_BL_PIN 25

void initDisplay() {
  // Backlight
  pinMode(TFT_BL_PIN, OUTPUT);
  analogWrite(TFT_BL_PIN, 255);  // full brightness; reduce for power saving

  tft.init();
  tft.setRotation(1);  // landscape — adjust 0-3 to match enclosure orientation
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);  // white text, black background (auto-clears)
}
```

### 2. Replace SD Card Init

**Before (standalone SD module, CS=5):**
```cpp
#include <SD.h>
#define SD_CS 5

void initSD() {
  if (!SD.begin(SD_CS)) {
    Serial.println("SD failed");
  }
}
```

**After (display-board SD slot, CS=15):**
```cpp
#include <SD.h>
#define SD_CS 15

void initSD() {
  // SD shares SPI bus with display — LCD_CS must be HIGH during SD access
  digitalWrite(5, HIGH);  // deselect LCD
  if (!SD.begin(SD_CS)) {
    Serial.println("SD failed");
  }
}
```

**Important:** The SD card and LCD share the SPI bus. Only one CS can be LOW at a time. The TFT_eSPI library handles its own CS, and the SD library handles its CS, so they should coexist. But during SD writes (logging), the display will not update — schedule display updates between SD flushes.

### 3. Replace All `display.*` Calls with `tft.*` Calls

The API is similar but not identical. Key mappings:

| SSD1306 (old) | TFT_eSPI (new) | Notes |
|---|---|---|
| `display.clearDisplay()` | `tft.fillScreen(TFT_BLACK)` | Full screen clear — avoid in loop (slow). Use `tft.fillRect()` for partial clears |
| `display.display()` | *(not needed)* | TFT_eSPI draws immediately, no buffer flush |
| `display.setTextSize(n)` | `tft.setTextSize(n)` or `tft.setTextFont(n)` | Use font numbers for better rendering |
| `display.setTextColor(WHITE)` | `tft.setTextColor(TFT_WHITE, TFT_BLACK)` | Second arg = background color (enables overwrite without clearing) |
| `display.setCursor(x, y)` | `tft.setCursor(x, y)` | Same API |
| `display.println(text)` | `tft.println(text)` | Same API |
| `display.drawLine(...)` | `tft.drawLine(...)` | Same API |

### 4. Redesign Display Layout

The old OLED was 128×64 monochrome — very constrained. The new 480×320 color screen allows a much richer layout.

**Recommended sailing dashboard layout (landscape, 480×320):**

```
┌─────────────────────────────────────────────────────┐
│  SAILFRAMES E1            SAT:24  FIX:3D  PPK      │  ← Status bar (20px)
├─────────────────────────┬───────────────────────────┤
│                         │                           │
│       5.8               │      247°                 │
│       kts               │      HDG                  │  ← Primary data (large fonts)
│       SOG               │                           │
│                         │                           │
├─────────────────────────┼───────────────────────────┤
│   HEEL: 12° S           │   TRIM: 3° B              │  ← IMU data
├─────────────────────────┼───────────────────────────┤
│   ● REC  S03            │   SD: OK   12:34:56 UTC   │  ← Recording status + time
└─────────────────────────┴───────────────────────────┘
```

**Color coding suggestions:**
- `TFT_GREEN` — recording active, good fix
- `TFT_RED` — recording stopped, errors, SD fail
- `TFT_YELLOW` — arming, searching for fix, warning states
- `TFT_CYAN` — speed and heading values
- `TFT_WHITE` — labels and static text
- `TFT_DARKGREY` — divider lines

### 5. Update Display Refresh Strategy

**Old (OLED):** Buffer entire 128×64 frame, then `display.display()` to flush. Simple, ~1KB buffer.

**New (TFT):** No frame buffer (too large: 480×320×2 = 307KB). Draw directly to screen. Use these techniques:

- **`tft.setTextColor(fg, bg)`** — set both foreground AND background color so text overwrites previous text without needing `fillRect()` clear first
- **Only redraw values that changed** — keep previous values in variables, compare before redrawing
- **Use `tft.setTextDatum()`** for right-aligned numbers so speed/heading values don't jump
- **Draw static labels once** in `setup()` or on first frame, then only update dynamic values in `loop()`
- **2Hz update rate** is fine (matches existing `DISPLAY_UPDATE_MS = 500`)

```cpp
// Example: efficient speed update (no flicker)
void updateSpeed(float sog) {
  static float lastSOG = -1;
  if (abs(sog - lastSOG) < 0.05) return;  // skip if unchanged
  lastSOG = sog;

  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.setTextDatum(TR_DATUM);  // top-right align
  tft.setTextFont(7);          // large 7-segment font
  tft.drawFloat(sog, 1, 200, 60, 7);  // 1 decimal place
}
```

### 6. Update Shutdown Display

**Before:**
```cpp
display.clearDisplay();
display.setTextSize(2);
display.setCursor(10, 20);
display.println("SHUTDOWN");
display.display();
```

**After:**
```cpp
tft.fillScreen(TFT_BLACK);
tft.setTextColor(TFT_RED, TFT_BLACK);
tft.setTextDatum(MC_DATUM);  // middle-center
tft.setTextFont(4);
tft.drawString("SHUTDOWN", 240, 160);
delay(1500);

// Turn off backlight before deep sleep
analogWrite(TFT_BL_PIN, 0);
```

### 7. Update Splash Screen

```cpp
void showSplash() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);

  tft.setTextFont(4);
  tft.drawString("SAILFRAMES", 240, 120);

  tft.setTextFont(2);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.drawString("E1 Fleet Tracker v2.0", 240, 160);

  delay(2000);
}
```

### 8. Backlight Power Management

```cpp
// Full brightness for sailing
analogWrite(TFT_BL_PIN, 255);

// Dim for dock / standby (saves ~60mA)
analogWrite(TFT_BL_PIN, 80);

// Off before deep sleep
analogWrite(TFT_BL_PIN, 0);
```

Consider auto-dimming when recording state is IDLE (docked) and full brightness when REC.

---

## SD Card: SPI Bus Sharing Notes

The LCD and SD card share MOSI/MISO/SCK with separate CS pins. The TFT_eSPI library and SD library each manage their own CS. However:

1. **Initialize SD after TFT** — call `tft.init()` first, then `SD.begin(SD_CS)`
2. **During SD writes, display won't update** — this is fine at 2Hz display refresh
3. **The existing SD mutex** (for dual-core access) still applies and should protect both LCD and SD SPI access
4. **If SD init fails**, try explicitly deselecting LCD CS first:
   ```cpp
   digitalWrite(TFT_CS, HIGH);  // ensure LCD deselected
   if (!SD.begin(SD_CS)) { ... }
   ```

---

## What Does NOT Change

These parts of the firmware remain identical:

- **GPS:** LG290P on UART2 (GPIO16/17, 460800 baud), RTCM3 frame parser, NMEA parsing
- **IMU:** BNO085 on I2C (GPIO21/22, 0x4A), GAME_ROTATION_VECTOR mode
- **Recording logic:** GPS speed-based auto-record (start >1.5kt/10s, stop <0.5kt/3min)
- **Power button:** GPIO13, 2-second hold for shutdown, ext0 deep sleep wake
- **Wi-Fi upload:** Dual-core architecture, Core 1 logging, Core 0 upload
- **File format:** Same CSV nav/imu files, same RTCM3 binary logging
- **Config.txt:** Same SD card config file format
- **Deep sleep:** Same ~10µA behavior

---

## Testing Checklist

- [ ] TFT displays splash screen on boot
- [ ] Backlight turns on and responds to PWM dimming
- [ ] SD card initializes via display-board SD slot (CS=GPIO15)
- [ ] SD logging works (nav CSV, imu CSV, RTCM3 binary)
- [ ] Display updates at 2Hz without flicker (use text overwrite, not fillScreen)
- [ ] Speed, heading, heel, trim values display correctly
- [ ] Recording state (READY/ARMING/REC/STOPPING) shows with correct colors
- [ ] Satellite count and fix type display correctly
- [ ] Shutdown shows "SHUTDOWN" text then turns off backlight
- [ ] Deep sleep current still < 50µA (backlight off)
- [ ] Display readable through polarized sunglasses in sunlight
- [ ] Display readable at heel angles (IPS viewing angle test)
- [ ] SPI bus contention: no corruption when SD writes and display update overlap
- [ ] No regression in GPS logging, IMU logging, or Wi-Fi upload
- [ ] Rotation setting (0-3) matches physical enclosure orientation

---

## Power Budget (Updated)

| Component | Current (3.3V) | Notes |
|---|---|---|
| ESP32 | ~80mA | Active, Wi-Fi off |
| LG290P | ~200mA | 10Hz, quad-band |
| BNO085 | ~12mA | GAME_ROTATION_VECTOR |
| ST7796 TFT | ~20mA | LCD controller |
| Backlight | ~95mA | 6 white LEDs, full brightness |
| SD card | ~30mA | During write bursts |
| **Total (sailing)** | **~440mA** | Wi-Fi off |
| **Total (upload)** | **~540mA** | Wi-Fi active on Core 0 |

With 6000mAh LiPo: ~13-14 hours sailing runtime.
With 3000mAh LiPo: ~6-7 hours sailing runtime.
