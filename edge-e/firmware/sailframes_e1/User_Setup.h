// ============================================================
// SailFrames E1 — TFT_eSPI User_Setup.h
// Hosyond 3.5" IPS ST7796U, 480x320, SPI
//
// Copy this file to your TFT_eSPI library folder, OR
// #define USER_SETUP_LOADED before including TFT_eSPI.h
// ============================================================

#define USER_SETUP_LOADED

#define ST7796_DRIVER

#define TFT_WIDTH  320
#define TFT_HEIGHT 480

// ESP32 SPI pin assignments
#define TFT_MOSI  23
#define TFT_MISO  25   // Swapped with BL to match soldered wiring
#define TFT_SCLK  18
#define TFT_CS     5
#define TFT_DC     2
#define TFT_RST    4

// Backlight pin
#define TFT_BL    19   // Swapped with MISO to match soldered wiring
#define TFT_BACKLIGHT_ON HIGH

// SPI frequency — 40MHz is safe for ST7796, can try 80MHz if stable
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
