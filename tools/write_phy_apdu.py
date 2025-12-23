#!/usr/bin/env python3
"""
write_phy_apdu.py

Change PHY fields by sending an APDU WRITE (rescue app) with TLV entries.

Usage examples:
  # set LED GPIO to 48
  python tools/write_phy_apdu.py --param led_gpio --value 48

  # set LED brightness to 128
  python tools/write_phy_apdu.py --param led_brightness --value 128

  # set LED driver to 3
  python tools/write_phy_apdu.py --param led_driver --value 3

  # set opts (integer bitfield) to 0x0001
  python tools/write_phy_apdu.py --param opts --value 0x1

  # set vid:pid (hex or decimal separated by ':')
  python tools/write_phy_apdu.py --param vidpid --value 0x1050:0x0407

Dependencies: 
- pyscard (python3-pyscard / pyscard)
- pcscd service must be running.
"""
import sys
import argparse
try:
    from smartcard.System import readers
except Exception:
    sys.stderr.write("pyscard is required. Install with: python3 -m pip install pyscard\n")
    sys.exit(1)

# Rescue AID
RESCUE_AID = [0xA0, 0x58, 0x3F, 0xC1, 0x9B, 0x7E, 0x4F, 0x21]

CLA_RESCUE = 0x80
INS_WRITE = 0x1C
P1_PHY = 0x01

# PHY tags
PHY_VIDPID = 0x0
PHY_LED_GPIO = 0x4
PHY_LED_BTNESS = 0x5
PHY_OPTS = 0x6
PHY_LED_DRIVER = 0xC

def find_reader():
    r = readers()
    if len(r) == 0:
        print("No PC/SC readers found.")
        return None
    print(f"Found readers: {[str(x) for x in r]}")
    return r[0]

def select_aid(conn, aid_bytes):
    apdu = [0x00, 0xA4, 0x04, 0x00, len(aid_bytes)] + aid_bytes
    resp, sw1, sw2 = conn.transmit(apdu)
    return resp, sw1, sw2

def build_tlv(param, value_str):
    if param == 'led_gpio':
        val = int(value_str, 0)
        return bytes([PHY_LED_GPIO, 1, val & 0xFF])
    if param == 'led_brightness':
        val = int(value_str, 0)
        return bytes([PHY_LED_BTNESS, 1, val & 0xFF])
    if param == 'led_driver':
        val = int(value_str, 0)
        return bytes([PHY_LED_DRIVER, 1, val & 0xFF])
    if param == 'opts':
        val = int(value_str, 0)
        b = val.to_bytes(2, 'big')
        return bytes([PHY_OPTS, 2]) + b
    if param == 'vidpid':
        # expect value like 'vid:pid' where vid and pid can be hex (0x) or decimal
        parts = value_str.split(':')
        if len(parts) != 2:
            raise ValueError('vidpid must be VID:PID')
        vid = int(parts[0], 0)
        pid = int(parts[1], 0)
        # serialize as big-endian VID then PID (matches phy_serialize_data)
        b = bytes([(vid >> 8) & 0xFF, vid & 0xFF, (pid >> 8) & 0xFF, pid & 0xFF])
        return bytes([PHY_VIDPID, 4]) + b
    raise ValueError('Unknown parameter')

def write_phy(conn, tlv_bytes):
    # Construct APDU: CLA INS P1 P2 Lc [data]
    apdu = [CLA_RESCUE, INS_WRITE, P1_PHY, 0x00, len(tlv_bytes)] + list(tlv_bytes)
    print("-> WRITE PHY APDU:", [hex(x) for x in apdu[:5]], "data=", tlv_bytes.hex())
    resp, sw1, sw2 = conn.transmit(apdu)
    print(f"<- SW: {hex(sw1)} {hex(sw2)}")
    return resp, sw1, sw2

def main():
    parser = argparse.ArgumentParser(description='Write PHY field via APDU (rescue app)')
    parser.add_argument('--param', required=True, choices=['led_gpio','led_brightness','led_driver','opts','vidpid'], help='Parameter to set')
    parser.add_argument('--value', required=True, help='Value to set (use 0x... for hex). For vidpid use VID:PID')
    args = parser.parse_args()

    rdr = find_reader()
    if not rdr:
        sys.exit(2)
    conn = rdr.createConnection()
    try:
        conn.connect()
    except Exception as e:
        print('Failed to connect to reader:', e)
        sys.exit(3)

    resp, sw1, sw2 = select_aid(conn, RESCUE_AID)
    if sw1 != 0x90:
        print('Select rescue AID failed or returned non-90 status, continuing (some readers still accept commands)')

    try:
        tlv = build_tlv(args.param, args.value)
    except ValueError as e:
        print('Error building TLV:', e)
        sys.exit(4)

    resp, sw1, sw2 = write_phy(conn, tlv)
    if sw1 == 0x90 and sw2 == 0x00:
        print('Write successful. You can verify with tools/read_phy_apdu.py')
    else:
        print('Write failed. SW=', hex(sw1), hex(sw2))

if __name__ == '__main__':
    main()
