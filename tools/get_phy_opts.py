#!/usr/bin/env python3
"""
get_phy_opts.py
Lit les options PHY via le vendor CBOR (CTAP_VENDOR_PHY_OPTS).

Usage:
  python get_phy_opts.py
"""
import sys
import cbor2
from fido2.hid import CtapHidDevice

# CTAP HID vendor-CBOR command (CTAP_VENDOR_CBOR = VENDOR_FIRST + 1)
CTAP_VENDOR_CBOR = 0x41
# Vendor subcommand for PHY options as défini dans firmware
CTAP_VENDOR_PHY_OPTS = 0x05

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
    # Le firmware renvoie le blob CBOR ; il y a parfois un octet d'offset en tête.
    # Essayer de décoder en ignorant le premier octet, sinon décoder tout.
    try:
        return cbor2.loads(resp[1:])
    except Exception:
        return cbor2.loads(resp)

def main():
    dev = find_device()
    if not dev:
        sys.exit(2)

    # vendorCmd = 0x01 (demande spécifique du handler)
    req_map = {1: 1}
    try:
        res = send_vendor_cbor(dev, CTAP_VENDOR_PHY_OPTS, req_map)
    except Exception as e:
        print("Erreur en envoyant la commande:", e)
        sys.exit(3)

    print("Réponse brute CBOR décodée :", res)
    if isinstance(res, dict) and 1 in res:
        print("PHY options (opts) =", res[1])
    else:
        print("Format inattendu, affichage complet :", res)

if __name__ == "__main__":
    main()