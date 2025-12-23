#!/usr/bin/env python3
"""
vendor_phy.py

Exemple : envoie une commande CTAP `CTAP_CONFIG` (subcommand vendor) nécessitant
une authentification PIN (pinUvAuthParam / PUAT). Permet de définir un paramètre
PHY (ex. LED GPIO) ou de lire des options.

Dépendances :
  python -m pip install fido2 cbor2

Usage :
  # Lire les options PHY (exemple) -- ici on montre comment authentifier si nécessaire
  python tools/vendor_phy.py --pin 12345678 --action read-opts

  # Définir la GPIO LED (exemple) à 5 (requiert PUAT)
  python tools/vendor_phy.py --pin 12345678 --set-led-gpio 5

Ce script montre la construction du payload CBOR attendu par `src/fido/cbor_config.c` :
  top-level map keys: 1=subcommand, 2=subpara (map), 3=pinUvAuthProtocol, 4=pinUvAuthParam

Le calcul de `pinUvAuthParam` suit l'implémentation firmware :
  verify_payload = 32 x 0xFF || 0x0D || <subcommand byte> || <raw_subpara_bytes>
  pinUvAuthParam = HMAC-SHA256(pin_token, verify_payload)[:16]  (protocol 1)

"""
import argparse
import getpass
import sys
import cbor2
import hmac
import hashlib
from fido2.hid import CtapHidDevice
from fido2.client import Fido2Client
from fido2.ctap2.pin import ClientPin

# CTAPHID / CTAP constants
CTAPHID_CBOR = 0x10
CTAP_CONFIG = 0x0D
SUBCMD_VENDOR = 0xFF

# CTAP config vendor command IDs (values copiés depuis src/fido/ctap.h)
CTAP_CONFIG_PHY_VIDPID = 0x6fcb19b0cbe3acfa
CTAP_CONFIG_PHY_LED_BTNESS = 0x76a85945985d02fd
CTAP_CONFIG_PHY_LED_GPIO = 0x7b392a394de9f948
CTAP_CONFIG_PHY_OPTS = 0x269f3b09eceb805f

def find_device():
    dev = next(CtapHidDevice.list_devices(), None)
    if not dev:
        print("Aucun périphérique FIDO/HID trouvé.")
        return None
    return dev

def get_pin_token(client, pin, permissions=0x20):
    # permissions default 0x20 == CTAP_PERMISSION_ACFG (authenticator config)
    cp = ClientPin(client._backend.ctap2)
    # Ensure protocol attribute exists (fallback to 1)
    protocol = getattr(cp, "protocol", 1)
    token = cp.get_pin_token(pin, permissions=permissions)
    return protocol, token

def compute_pin_uv_auth_param(pin_token: bytes, protocol: int, subcommand: int, raw_subpara: bytes) -> bytes:
    # verify_payload = 32 x 0xFF || CTAP_CONFIG || subcommand || raw_subpara
    verify_payload = (b"\xff" * 32) + bytes([CTAP_CONFIG, subcommand]) + raw_subpara
    mac = hmac.new(pin_token, verify_payload, hashlib.sha256).digest()
    if protocol == 1:
        return mac[:16]
    else:
        return mac

def send_ctap_config(device, cbor_map):
    payload = bytes([CTAP_CONFIG]) + cbor2.dumps(cbor_map)
    resp = device.call(CTAPHID_CBOR, payload)
    # Try to decode skipping the first byte (firmware places response at offset)
    try:
        return cbor2.loads(resp[1:])
    except Exception:
        return cbor2.loads(resp)

def action_read_opts(device, client=None, pin=None):
    # We'll build a vendor CTAP_CONFIG request for PHY_OPTS (vendor subcommand expects nested map with vendorCmd=CTAP_CONFIG_PHY_OPTS)
    nested = {1: CTAP_CONFIG_PHY_OPTS}
    raw_sub = cbor2.dumps(nested)

    if pin:
        if client is None:
            client = Fido2Client(device, "https://example.com")
        protocol, pin_token = get_pin_token(client, pin)
        pinuv = compute_pin_uv_auth_param(pin_token, protocol, SUBCMD_VENDOR, raw_sub)
        cbor_map = {1: SUBCMD_VENDOR, 2: nested, 3: protocol, 4: pinuv}
    else:
        # Try without auth (may be rejected)
        cbor_map = {1: SUBCMD_VENDOR, 2: nested}

    res = send_ctap_config(device, cbor_map)
    print("Réponse CBOR décodée:")
    print(res)

def action_set_led_gpio(device, gpio, client=None, pin=None):
    nested = {1: CTAP_CONFIG_PHY_LED_GPIO, 3: int(gpio)}
    raw_sub = cbor2.dumps(nested)

    if pin is None:
        print("Cette commande requiert pinUvAuth (PUAT). Passez --pin ou utilisez --interactive-pin")
        return

    if client is None:
        client = Fido2Client(device, "https://example.com")
    protocol, pin_token = get_pin_token(client, pin)
    pinuv = compute_pin_uv_auth_param(pin_token, protocol, SUBCMD_VENDOR, raw_sub)
    cbor_map = {1: SUBCMD_VENDOR, 2: nested, 3: protocol, 4: pinuv}

    res = send_ctap_config(device, cbor_map)
    print("Réponse CBOR décodée:")
    print(res)

def main():
    parser = argparse.ArgumentParser(description="Exemple: CTAP CTAP_CONFIG vendor with PIN auth (PUAT)")
    parser.add_argument("--pin", help="PIN (optionnel). Si non fourni et nécessaire, utilisez --interactive-pin")
    parser.add_argument("--interactive-pin", action="store_true", help="Demander PIN en mode interactif")
    parser.add_argument("--action", choices=["read-opts", "set-led-gpio"], default="read-opts")
    parser.add_argument("--set-led-gpio", type=int, help="Numéro GPIO à écrire (utilisé avec --action set-led-gpio)")
    args = parser.parse_args()

    device = find_device()
    if device is None:
        sys.exit(2)

    pin = args.pin
    if args.interactive_pin:
        pin = getpass.getpass("PIN: ")

    client = None
    # Construct Fido2Client lazily when pin needed

    if args.action == "read-opts":
        action_read_opts(device, client=client, pin=pin)
    elif args.action == "set-led-gpio":
        if args.set_led_gpio is None:
            print("Indiquez --set-led-gpio N")
            sys.exit(3)
        # instantiate client when using PIN
        if pin:
            client = Fido2Client(device, "https://example.com")
        action_set_led_gpio(device, args.set_led_gpio, client=client, pin=pin)

if __name__ == "__main__":
    main()
