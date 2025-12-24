#!/usr/bin/env python3
"""
read_phy_apdu.py

Attempt to read `EF_PHY` from the device using the CCID/APDU rescue app.

This script:
 - selects the rescue AID
 - sends the APDU CLA=0x80 INS=0x1E P1=0x01 (read PHY)
 - parses the returned serialized PHY blob and prints LED GPIO, brightness,
   driver and opts (flags).

Dependencies:
- pyscard (python3-pyscard / pyscard)
- pcscd service must be running.

Usage:
  python tools/read_phy_apdu.py

Driver Values:
    1 → PICO (LED board pin)
    2 → PIMORONI
    3 → WS2812 (addressable)
    4 → CYW43 (if enabled)
    5 → NEOPIXEL (ESP)
    255 (0xFF) → NONE

Note: If your device does not expose the CCID/rescue app, the script will
report the responses from the reader. The management app (AID shown in logs)
may also be available; this script focuses on the rescue app which provides
an explicit `READ` for `PHY` (see `pico-keys-sdk/src/rescue.c`).
"""
import sys
try:
    from smartcard.System import readers
except Exception as exc:
    import sys
    sys.stderr.write("Module 'pyscard' (smartcard) not found.\n")
    sys.stderr.write("Install the dependency and ensure the PC/SC service is running, then re-run this script. Example (Debian/Ubuntu):\n")
    sys.stderr.write("  sudo apt update && sudo apt install -y pcscd libpcsclite-dev build-essential python3-dev\n")
    sys.stderr.write("  python3 -m pip install pyscard\n")
    sys.stderr.write("Then start the PC/SC service if needed:\n")
    sys.stderr.write("  sudo systemctl start pcscd\n")
    sys.stderr.write("Check available readers with:\n")
    sys.stderr.write("  pcsc_scan\n")
    sys.stderr.write("Or install the prepackaged Python binding if available:\n")
    sys.stderr.write("  sudo apt install -y python3-pyscard\n")
    sys.exit(1)

# Rescue AID (8 bytes) as defined in pico-keys-sdk/src/rescue.c
RESCUE_AID = [0xA0, 0x58, 0x3F, 0xC1, 0x9B, 0x7E, 0x4F, 0x21]

# APDU constants
CLA_RESCUE = 0x80
INS_READ = 0x1E
P1_PHY = 0x01

# PHY tags from pico-keys-sdk/src/fs/phy.h
PHY_VIDPID = 0x0
PHY_LED_GPIO = 0x4
PHY_LED_BTNESS = 0x5
PHY_OPTS = 0x6
PHY_UP_BTN = 0x8
PHY_USB_PRODUCT = 0x9
PHY_LED_DRIVER = 0xC

def find_reader():
    r = readers()
    if len(r) == 0:
        print("No PC/SC readers found.")
        return None
    print(f"Found readers: {[str(x) for x in r]}")
    return r[0]

def to_bytes(lst):
    return bytes(lst)

def select_aid(conn, aid_bytes):
    apdu = [0x00, 0xA4, 0x04, 0x00, len(aid_bytes)] + aid_bytes
    print(f"-> SELECT AID: {[hex(x) for x in apdu]}")
    resp, sw1, sw2 = conn.transmit(apdu)
    print(f"<- SW: {hex(sw1)} {hex(sw2)}")
    return resp, sw1, sw2

def read_phy(conn):
    # CLA=0x80 INS=0x1E P1=0x01 P2=0x00 Le=0x00 (request max)
    apdu = [CLA_RESCUE, INS_READ, P1_PHY, 0x00, 0x00]
    print(f"-> READ PHY APDU: {[hex(x) for x in apdu]}")
    resp, sw1, sw2 = conn.transmit(apdu)
    print(f"<- SW: {hex(sw1)} {hex(sw2)}")
    return bytes(resp), sw1, sw2

def parse_phy_blob(data: bytes):
    i = 0
    parsed = {}
    length = len(data)
    while i + 2 <= length:
        tag = data[i]; i += 1
        tlen = data[i]; i += 1
        if i + tlen > length:
            print("Malformed PHY blob: length exceeds buffer")
            break
        val = data[i:i+tlen]; i += tlen
        parsed[tag] = val
    return parsed

def decode_and_print(parsed):
    def u8(b):
        return int.from_bytes(b, 'big') if len(b) > 0 else None

    print("Parsed PHY fields:")
    if PHY_LED_GPIO in parsed:
        print(f" - LED GPIO: {u8(parsed[PHY_LED_GPIO])}")
    else:
        print(" - LED GPIO: not present")

    if PHY_LED_BTNESS in parsed:
        print(f" - LED Brightness: {u8(parsed[PHY_LED_BTNESS])}")
    else:
        print(" - LED Brightness: not present")

    if PHY_LED_DRIVER in parsed:
        print(f" - LED Driver: {u8(parsed[PHY_LED_DRIVER])}")
    else:
        print(" - LED Driver: not present")

    if PHY_OPTS in parsed:
        opts = int.from_bytes(parsed[PHY_OPTS], 'big')
        print(f" - PHY_OPTS (raw): 0x{opts:04x} ({opts})")
        # Known flags
        flags = []
        if opts & 0x1:
            flags.append('PHY_OPT_WCID')
        if opts & 0x2:
            flags.append('PHY_OPT_DIMM')
        if opts & 0x4:
            flags.append('PHY_OPT_DISABLE_POWER_RESET')
        if opts & 0x8:
            flags.append('PHY_OPT_LED_STEADY')
        if flags:
            print(f"   Flags: {', '.join(flags)}")
        else:
            print("   Flags: (none of the known PHY_OPT_*)")
        unknown = opts & ~0xF
        if unknown:
            print(f"   Unknown bits: 0x{unknown:04x}")
    else:
        print(" - PHY_OPTS: not present")

    if PHY_VIDPID in parsed:
        b = parsed[PHY_VIDPID]
        if len(b) == 4:
            # Firmware serializes vidpid with byte order mixing; to get VID/PID
            # follow phy_unserialize_data behaviour partially
            # b[0..3] correspond to the sequence written in phy_serialize_data
            # which was: phy->vidpid[1], phy->vidpid[0], phy->vidpid[3], phy->vidpid[2]
            vid = (b[0] << 8) | b[1]
            pid = (b[2] << 8) | b[3]
            print(f" - VID: 0x{vid:04x}, PID: 0x{pid:04x}")
        else:
            print(f" - VIDPID: raw ({len(b)} bytes): {b.hex()}")
    else:
        print(" - VID/PID: not present")

def main():
    rdr = find_reader()
    if not rdr:
        sys.exit(2)
    conn = rdr.createConnection()
    try:
        conn.connect()
    except Exception as e:
        print("Failed to connect to reader:", e)
        sys.exit(3)

    # Select rescue AID
    resp, sw1, sw2 = select_aid(conn, RESCUE_AID)
    if sw1 != 0x90:
        print("Select rescue AID failed, trying management AID fallback...")
    # Try read PHY via rescue APDU
    data, sw1, sw2 = read_phy(conn)
    if sw1 == 0x90 and sw2 == 0x00:
        print(f"Received {len(data)} bytes from READ PHY")
        parsed = parse_phy_blob(data)
        decode_and_print(parsed)
    else:
        print("READ PHY APDU failed or returned no data. SW=", hex(sw1), hex(sw2))

if __name__ == '__main__':
    main()
