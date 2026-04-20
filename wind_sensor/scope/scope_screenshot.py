#!/usr/bin/env python3
"""Capture screenshot from Siglent SDS1104X-E oscilloscope over Ethernet."""

import socket
import time
import io

SCOPE_IP = "10.10.4.2"
PORT = 5025
OUTPUT_FILE = "scope_capture.png"

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SCOPE_IP, PORT))
    s.settimeout(5)

    # Request screen dump
    s.sendall(b"SCDP\n")
    time.sleep(1)

    # Receive the BMP image data
    data = b""
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
        except socket.timeout:
            break

    s.close()

    if len(data) > 0:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            img.save(OUTPUT_FILE)
            print(f"Screenshot saved to {OUTPUT_FILE} ({img.size[0]}x{img.size[1]})")
        except ImportError:
            fallback = OUTPUT_FILE.replace('.png', '.bmp')
            with open(fallback, "wb") as f:
                f.write(data)
            print(f"Pillow not installed. Saved as {fallback}")
            print("Install with: pip3 install Pillow")
    else:
        print("No data received")

if __name__ == "__main__":
    main()