// E1 fleet-tracker bill of materials (ported from the legacy bom.html — static
// hardware reference content, kept as typed data so the page is pure markup).
export interface BomPart {
  ref: string;
  part: string;
  qty: string;
  price: string;
  source: string;
}

export interface BomGroup {
  key: string; // i18n key under bom.groups
  subtotal: string;
  parts: BomPart[];
}

export const BOM_COMMON: BomGroup = {
  key: "common",
  subtotal: "~$120–155",
  parts: [
    { ref: "1", part: "ELEGOO ESP32 DevKit V1 (CP2102, USB-C)", qty: "1", price: "$8–10", source: "Amazon" },
    { ref: "2", part: "GY-BNO08X (BNO085) IMU breakout", qty: "1", price: "$15–25", source: "Amazon" },
    { ref: "3", part: "microSD adapter module (SPI, 3.3 V level shifters)", qty: "1", price: "$5–7", source: "Amazon" },
    { ref: "4", part: "microSD card, 32 GB Class 10", qty: "1", price: "$8–10", source: "Amazon" },
    { ref: "5", part: "DWEII USB-C 5 V 2 A boost charger (TP4056 + boost)", qty: "1", price: "$9–12", source: "Amazon" },
    { ref: "6", part: "LiPo 3.7 V 6000 mAh, 906090 cell, JST PH 2.0", qty: "1", price: "$18–25", source: "Amazon" },
    { ref: "7", part: "YETLEBOX IP67 ABS enclosure, clear lid", qty: "1", price: "$13–18", source: "Amazon" },
    { ref: "8", part: "SPDT slide switch, panel-mount", qty: "1", price: "$5 / 10-pack", source: "Amazon" },
    { ref: "9", part: "Resistor kit (2× 100 kΩ divider, 2× 4.7 kΩ I²C pull-ups)", qty: "1 kit", price: "$10–15", source: "Amazon" },
    { ref: "10", part: "JST PH 2.0 mm pre-crimped pigtail kit", qty: "1 kit", price: "$7–10", source: "Amazon" },
    { ref: "11", part: "Dupont jumper wires (M/F + F/F, 20 cm)", qty: "1 set", price: "$6–8", source: "Amazon" },
    { ref: "12", part: "M2.5 standoffs + screws kit", qty: "1 kit", price: "$8–10", source: "Amazon" },
    { ref: "13", part: "Heat-shrink tubing assortment", qty: "1 kit", price: "$6–8", source: "Amazon" },
    { ref: "14", part: "KiCad PCB v1.1 (60.5×91.5 mm, 2-layer)", qty: "1", price: "~$5/board (5-pack)", source: "JLCPCB / PCBWay" },
  ],
};

export const BOM_OPTION_A: BomGroup = {
  key: "optionA",
  subtotal: "~$110",
  parts: [
    { ref: "A1", part: "Waveshare LG290P GNSS Module + active antenna", qty: "1", price: "~$109", source: "Waveshare" },
    { ref: "A2", part: "(Optional) external high-gain GNSS antenna, SMA", qty: "1", price: "$15–25", source: "Amazon" },
  ],
};

export const BOM_OPTION_B: BomGroup = {
  key: "optionB",
  subtotal: "~$30–40",
  parts: [
    { ref: "B1", part: "Waveshare LC29H (DA) GNSS Module + active antenna", qty: "1", price: "~$30–40", source: "Waveshare" },
    { ref: "B2", part: "(Optional) external L1/L5 active antenna, SMA", qty: "1", price: "$15–25", source: "Amazon" },
  ],
};

export const BOM_OPTIONAL: BomGroup = {
  key: "optional",
  subtotal: "",
  parts: [
    { ref: "O1", part: "Hosyond 3.5\" IPS TFT, ST7796U, 480×320, SPI", qty: "1", price: "$15–20", source: "Amazon" },
    { ref: "O2", part: "Adafruit DPS310 barometric pressure breakout (I²C)", qty: "1", price: "$7–12", source: "Amazon" },
    { ref: "O3", part: "Amphenol LTW VENT-PS1 IP67 pressure vent", qty: "1", price: "$4–8", source: "Digi-Key" },
  ],
};

export const BOM_TOTALS: Array<{ config: string; total: string }> = [
  { config: "Option A (LG290P), with display", total: "~$245–250" },
  { config: "Option A (LG290P), headless", total: "~$225–230" },
  { config: "Option B (LC29H), with display", total: "~$165–170" },
  { config: "Option B (LC29H), headless", total: "~$145–150" },
];
