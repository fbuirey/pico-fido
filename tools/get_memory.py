#!/usr/bin/env python3
"""
get_memory.py
Lit les statistiques mémoire via le vendor CBOR (CTAP_VENDOR_MEMORY).

Usage:
  python get_memory.py
"""
import sys
import cbor2
from fido2.hid import CtapHidDevice

CTAP_VENDOR_CBOR = 0x41
CTAP_VENDOR_MEMORY = 0x06

def find_device():
    dev = next(CtapHidDevice.list_devices(), None)
    if not dev:
        print("Aucun périphérique FIDO trouvé (HID).")
        return None
    return dev

def send_vendor_cbor(device, vendor_cmd, cbor_map):
    payload = bytes([vendor_cmd]) + cbor2.dumps(cbor_map)
    resp = device.call(CTAP_VENDOR_CBOR, payload)
    if not resp:
        return None
    try:
        return cbor2.loads(resp[1:])
    except Exception:
        return cbor2.loads(resp)

def main():
    dev = find_device()
    if not dev:
        sys.exit(2)

    req_map = {1: 1}
    try:
        res = send_vendor_cbor(dev, CTAP_VENDOR_MEMORY, req_map)
    except Exception as e:
        print("Erreur en envoyant la commande:", e)
        sys.exit(3)

    print("Réponse brute CBOR décodée :", res)
    if isinstance(res, dict) and 1 in res:
        # cbor_vendor retourne un map avec paires (1..5)
        print("Flash free space:", res.get(1))
        print("Flash used space:", res.get(2))
        print("Flash total space:", res.get(3))
        print("Number of files:", res.get(4))
        print("Flash size:", res.get(5))
    else:
        print("Format inattendu, affichage complet :", res)

if __name__ == "__main__":
    main()