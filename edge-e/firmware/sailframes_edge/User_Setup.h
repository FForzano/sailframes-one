// ============================================================
// SailFrames Edge — TFT_eSPI User_Setup.h
//   E (LG290P):  Hosyond 3.5" IPS ST7796U, 480x320, SPI       (default)
//   B (LC29HEA): Hosyond 2.8" IPS ILI9341V, 240x320, SPI      (-DBUILD_B1)
//
// #define USER_SETUP_LOADED is set here so TFT_eSPI uses THIS file
// (it is #included by sailframes_edge.ino before <TFT_eSPI.h>).
// ============================================================

#define USER_SETUP_LOADED

#ifdef BUILD_B1
  // ---- B1: 2.8" 240x320 ILI9341V, 4-line SPI ----
  // Capacitive touch (FT6336G, I2C) is a SEPARATE chip and is NOT wired on B1
  // (J9 CTP_SCL = NC) — unused.
  #define ILI9341_DRIVER
  #define TFT_WIDTH  240
  #define TFT_HEIGHT 320
  // ⚠ Do NOT define TFT_BL on B1: GPIO19 is PWR_HOLD (the v0.13 self-power
  // latch). TFT_eSPI must never drive GPIO19. The real backlight is GPIO25,
  // PWM'd by the firmware (TFT_BL_PIN in the .ino). B1's TFT MISO is not wired
  // (J9 SDO_MISO = NC).
  #define TFT_MISO  -1
#else
  // ---- E: 3.5" 320x480 ST7796U ----
  #define ST7796_DRIVER
  #define TFT_WIDTH  320
  #define TFT_HEIGHT 480
  #define TFT_MISO  25   // Swapped with BL to match soldered E1 wiring
  #define TFT_BL    19   // Swapped with MISO to match soldered E1 wiring
  #define TFT_BACKLIGHT_ON HIGH
#endif

// ESP32 SPI pin assignments (common to both displays)
#define TFT_MOSI  23
#define TFT_SCLK  18
#define TFT_CS     5
#define TFT_DC     2
#define TFT_RST    4

// SPI frequency — 40MHz is safe for both ST7796 and ILI9341
#define SPI_FREQUENCY       40000000
#define SPI_READ_FREQUENCY  20000000
#define SPI_TOUCH_FREQUENCY  2500000

// Enable SPI transactions for proper bus arbitration with SD card
#define SUPPORT_TRANSACTIONS

// Fonts — load only what's needed to save flash
#define LOAD_GLCD    // 8px font
#define LOAD_FONT2   // 16px font
#define LOAD_FONT4   // 26px font
#define LOAD_FONT6   // 48px numeric font
#define LOAD_FONT7   // 48px 7-segment font
#define LOAD_FONT8   // 75px numeric font
#define LOAD_GFXFF   // FreeFonts support
#define SMOOTH_FONT
