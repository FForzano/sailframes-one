/*
 * SailFrames E1 — LG290P bootstrap configuration
 * ----------------------------------------------
 *
 * One-shot routine that brings a fresh or wiped LG290P up to the SailFrames
 * fleet standard, then saves to NVM. Designed to be called once from setup()
 * when a flag in /config.txt is set:
 *
 *     gps_bootstrap=1
 *
 * On success, the bootstrap clears the flag (rewrites config.txt) and reboots.
 *
 * The configuration matches lg290p_configure.py — keep both in sync.
 *
 * Dependencies: HardwareSerial (built-in), SD (built-in)
 *
 * Usage in main firmware:
 *
 *     #include "lg290p_bootstrap.h"
 *     ...
 *     // After SD.begin() and Serial2.begin() succeed:
 *     if (LG290P_Bootstrap::isRequested("/config.txt")) {
 *         LG290P_Bootstrap::run(Serial2, "/config.txt");
 *         ESP.restart();
 *     }
 */

#ifndef LG290P_BOOTSTRAP_H
#define LG290P_BOOTSTRAP_H

#include <Arduino.h>
#include <HardwareSerial.h>
#include <SD.h>

namespace LG290P_Bootstrap {

// Bauds the LG290P supports, in the order we'll probe.
// 460800 first because it's where we leave configured units.
static const uint32_t kSupportedBauds[] = {460800, 9600, 115200, 230400, 921600};
static const size_t kNumBauds = sizeof(kSupportedBauds) / sizeof(kSupportedBauds[0]);

// Configuration steps in order. Empty payload = end of list.
struct Step {
    const char* label;
    const char* payload;  // without leading '$' or trailing '*XX\r\n'
};

static const Step kConfigSteps[] = {
    {"rover mode",          "PQTMCFGRCVRMODE,W,1"},
    {"constellations",      "PQTMCFGCNST,W,1,1,1,1,1,0"},
    {"10 Hz fix",           "PQTMCFGFIXRATE,W,100"},
    {"RTCM MSM7+EPH",       "PQTMCFGRTCM,W,7,0,-90,07,06,3,0"},
    {"RTCM3 GPS MSM",       "PQTMCFGMSGRATE,W,RTCM3-107X,1,0"},
    {"RTCM3 GLO MSM",       "PQTMCFGMSGRATE,W,RTCM3-108X,1,0"},
    {"RTCM3 GAL MSM",       "PQTMCFGMSGRATE,W,RTCM3-109X,1,0"},
    {"RTCM3 BDS MSM",       "PQTMCFGMSGRATE,W,RTCM3-112X,1,0"},
    {"RTCM3 1019 GPSeph",   "PQTMCFGMSGRATE,W,RTCM3-1019,1"},
    {"RTCM3 1020 GLOeph",   "PQTMCFGMSGRATE,W,RTCM3-1020,1"},
    {"RTCM3 1044 QZSeph",   "PQTMCFGMSGRATE,W,RTCM3-1044,1"},
    {"GGA 1Hz",             "PQTMCFGMSGRATE,W,GGA,10"},
    {"RMC 1Hz",             "PQTMCFGMSGRATE,W,RMC,10"},
    {"UART3 460800",        "PQTMCFGUART,W,3,460800,8,0,1,0"},
    {"save to flash",       "PQTMSAVEPAR"},
    {nullptr, nullptr}
};

// Compute NMEA XOR checksum of payload (everything between $ and *).
inline uint8_t checksum(const char* s) {
    uint8_t c = 0;
    while (*s) c ^= (uint8_t)*s++;
    return c;
}

// Send a payload as a complete $...*XX\r\n NMEA sentence.
inline void sendCommand(HardwareSerial& gps, const char* payload) {
    gps.printf("$%s*%02X\r\n", payload, checksum(payload));
    gps.flush();
}

// Drain the receive buffer for `ms` milliseconds.
inline void drain(HardwareSerial& gps, uint32_t ms) {
    uint32_t start = millis();
    while (millis() - start < ms) {
        while (gps.available()) gps.read();
        delay(1);
    }
}

// Wait for "$<cmdName>,OK" within `timeoutMs`. Returns true on OK.
inline bool waitForOk(HardwareSerial& gps, const char* cmdName, uint32_t timeoutMs) {
    char expected[48];
    snprintf(expected, sizeof(expected), "$%s,OK", cmdName);
    char errExpected[48];
    snprintf(errExpected, sizeof(errExpected), "$%s,ERROR", cmdName);

    char buf[256];
    size_t idx = 0;
    uint32_t start = millis();
    while (millis() - start < timeoutMs) {
        while (gps.available()) {
            char c = (char)gps.read();
            if (idx < sizeof(buf) - 1) {
                buf[idx++] = c;
                buf[idx] = 0;
                if (strstr(buf, expected)) return true;
                if (strstr(buf, errExpected)) return false;
            } else {
                // Slide buffer if it fills up
                memmove(buf, buf + 128, idx - 128);
                idx -= 128;
                buf[idx] = 0;
            }
        }
        delay(2);
    }
    return false;
}

// Try each supported baud; return the one where we see fresh NMEA traffic.
// Returns 0 on failure.
inline uint32_t detectBaud(HardwareSerial& gps, int rxPin, int txPin) {
    for (size_t i = 0; i < kNumBauds; i++) {
        uint32_t baud = kSupportedBauds[i];
        gps.end();
        gps.begin(baud, SERIAL_8N1, rxPin, txPin);
        delay(100);
        // Flush, then look for a '$' + valid-looking checksum within 1.5s
        while (gps.available()) gps.read();
        uint32_t start = millis();
        bool sawDollar = false;
        bool sawStar = false;
        size_t bytes = 0;
        while (millis() - start < 1500) {
            if (gps.available()) {
                char c = (char)gps.read();
                bytes++;
                if (c == '$') sawDollar = true;
                if (sawDollar && c == '*') sawStar = true;
                if (sawStar && bytes > 10) {
                    Serial.printf("  Detected NMEA at %u baud\n", baud);
                    return baud;
                }
            } else {
                delay(2);
            }
        }
        Serial.printf("  No NMEA at %u baud\n", baud);
    }
    return 0;
}

// Extract command name (e.g. "PQTMCFGUART") from a payload like "PQTMCFGUART,W,3,...".
inline void extractCmdName(const char* payload, char* out, size_t outSize) {
    size_t i = 0;
    while (payload[i] && payload[i] != ',' && i < outSize - 1) {
        out[i] = payload[i];
        i++;
    }
    out[i] = 0;
}

// Check whether bootstrap is requested via config.txt.
inline bool isRequested(const char* configPath) {
    File f = SD.open(configPath, FILE_READ);
    if (!f) return false;
    bool found = false;
    while (f.available()) {
        String line = f.readStringUntil('\n');
        line.trim();
        if (line == "gps_bootstrap=1") {
            found = true;
            break;
        }
    }
    f.close();
    return found;
}

// Clear the gps_bootstrap=1 flag from config.txt by rewriting the file.
inline bool clearRequest(const char* configPath) {
    File f = SD.open(configPath, FILE_READ);
    if (!f) return false;
    String contents;
    while (f.available()) {
        String line = f.readStringUntil('\n');
        line.trim();
        if (line.length() == 0) continue;
        if (line == "gps_bootstrap=1") continue;
        contents += line + "\n";
    }
    f.close();

    SD.remove(configPath);
    File w = SD.open(configPath, FILE_WRITE);
    if (!w) return false;
    w.print(contents);
    w.close();
    return true;
}

// Run the full bootstrap sequence. Returns number of failed steps (0 = success).
// Caller should ESP.restart() after this returns.
inline int run(HardwareSerial& gps, const char* configPath,
               int rxPin = 16, int txPin = 17) {
    Serial.println(F("=== LG290P bootstrap starting ==="));

    uint32_t baud = detectBaud(gps, rxPin, txPin);
    if (baud == 0) {
        Serial.println(F("ERROR: no LG290P detected on UART2 — check wiring and power"));
        return -1;
    }

    Serial.printf("Connected at %u baud — applying configuration\n", baud);

    int failures = 0;
    for (const Step* step = kConfigSteps; step->label != nullptr; step++) {
        char cmdName[32];
        extractCmdName(step->payload, cmdName, sizeof(cmdName));

        drain(gps, 50);
        sendCommand(gps, step->payload);

        if (waitForOk(gps, cmdName, 2000)) {
            Serial.printf("  OK   %s\n", step->label);
        } else {
            Serial.printf("  FAIL %s\n", step->label);
            failures++;
        }
    }

    // Hot restart so settings apply immediately
    drain(gps, 50);
    sendCommand(gps, "PQTMHOT");
    delay(500);

    if (failures == 0) {
        Serial.println(F("=== Bootstrap SUCCESS — clearing flag and rebooting ==="));
        clearRequest(configPath);
    } else {
        Serial.printf("=== Bootstrap completed with %d failures (flag NOT cleared) ===\n",
                      failures);
    }

    return failures;
}

} // namespace LG290P_Bootstrap

#endif // LG290P_BOOTSTRAP_H
