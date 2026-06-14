# B1 J5 microSD — pinout fix (v0.12 → next rev)

**Status: BLOCKING bug. SD is dead on every v0.12 board (boards 0002 + 0004 confirmed,
two known-good cards). It is a routing/netlist error, not a solder defect — not
reworkable on the fabbed boards. This change is required before the 30-unit build.**

## The bug

`J5` was drawn with a **generic `Connector_Generic:Conn_01x07`** symbol, and the six
signals + CD were wired to its pins **1–7 in SPI-logical order**:

```
pin1=HSPI_CS  pin2=HSPI_MOSI  pin3=HSPI_MISO  pin4=HSPI_SCK  pin5=V3V3  pin6=GND  pin7=SD_CD
```

But the footprint `Connector_Card:microSD_HC_Hirose_DM3D-SF` numbers its pads **1–8 =
the microSD CARD pins 1–8** (DAT2, DAT3, CMD, VDD, CLK, VSS, DAT0, DAT1; pads 9/10 =
card-detect switch; SH = shield). Symbol pin N → pad N → card pin N, so every signal
lands on the wrong physical contact:

| Pad | Card pin (physical) | SPI fn | v0.12 (WRONG) | Effect |
|---:|---|---|---|---|
| 1 | DAT2 | — | HSPI_CS | CS on an unused contact |
| 2 | DAT3 | **CS** | HSPI_MOSI | CS line gets MOSI |
| 3 | CMD | **MOSI** | HSPI_MISO | MOSI line gets MISO |
| 4 | **VDD (power)** | **VDD** | **HSPI_SCK** | **card never powered — VDD pin sees the clock** |
| 5 | CLK | **SCK** | **V3V3** | **no clock — CLK contact sits at static 3.3 V** |
| 6 | VSS | GND | GND | ✅ only correct pin (coincidence) |
| 7 | DAT0 | **MISO** | SD_CD | MISO line gets card-detect |

Card gets no power and no clock → cannot enumerate at any speed. Passed ERC (nets
connected) and DRC (routing legal) because the nets *are* connected — just to the
wrong pads.

## The fix (do this in the schematic, then re-route + re-fab)

Replace the `Conn_01x07` with a symbol that exposes pads 1–10 — either
`Connector_Generic:Conn_01x10`, or a proper microSD socket symbol
(e.g. `Connector:microSD_SocketHC`) — and connect each net to the **correct pad
number** below. Firmware SD pins (CLK=14, MOSI=13, MISO=35, CS=27) and the pin-map
nets are already correct; **only the J5 net→pad assignment changes.**

| Pad | Card pin | Connect to | Note |
|---:|---|---|---|
| 1 | DAT2 | V3V3 via 100 kΩ (or NC) | pull high to keep card out of SD 4-bit mode (optional) |
| 2 | DAT3 | **HSPI_CS** | |
| 3 | CMD | **HSPI_MOSI** | |
| 4 | VDD | **V3V3** | keep the 10 µF + 100 nF decoupling here |
| 5 | CLK | **HSPI_SCK** | |
| 6 | VSS | **GND** | unchanged |
| 7 | DAT0 | **HSPI_MISO** | |
| 8 | DAT1 | V3V3 via 100 kΩ (or NC) | optional, as pad 1 |
| 9 | CD switch | **SD_CD** + 10 kΩ to V3V3 | optional — firmware ignores CD; leave NC if unused |
| 10 | CD switch | **GND** | other side of the detect switch |

### Net-by-net delta from v0.12
- `HSPI_CS`: pad 1 → **pad 2**
- `HSPI_MOSI`: pad 2 → **pad 3**
- `HSPI_MISO`: pad 3 → **pad 7**
- `HSPI_SCK`: pad 4 → **pad 5**
- `V3V3`: pad 5 → **pad 4**
- `GND`: pad 6 → **pad 6** (no change)
- `SD_CD`: pad 7 → **pad 9** (or drop entirely; CD is unused in firmware)

### Keep as-is
- The **10 kΩ pull-ups** on HSPI_CS/MOSI/MISO/SCK are net-attached — they follow the
  nets to the new pads automatically; no change needed.
- V3V3 decoupling moves with V3V3 to pad 4.

## Verify after the change
1. ERC + DRC clean.
2. **Net-trace each DevKit GPIO → J5 physical pad** (don't trust ERC): GPIO14→pad5(CLK),
   GPIO13→pad3(CMD), GPIO35→pad7(DAT0), GPIO27→pad2(DAT3), V3V3→pad4(VDD), GND→pad6.
3. On the re-fabbed board, flash `edge-b/firmware/b1_bringup` and run `sd` — expect
   `OK` + `write/read/delete round-trip PASS`.

## While you're in this rev
Also add the **2.4 GHz external-antenna provision** (the other build-gating issue —
see the ESP-NOW range/antenna notes): DevKit antenna overhang + ground-pour keepout,
or move to a soldered WROOM-32U + U.FL. Both blockers close in one spin.

## The 5 existing v0.12 boards
SD is physically misrouted — not fixable by rework. They remain usable as USB-powered
dev units for everything *except* SD logging.
