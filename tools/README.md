# Tools README

## CTAP Vendor CBOR Commnands

This folder contains small utility scripts to interact with the Pico FIDO firmware using CTAP vendor CBOR commands over the HID transport.

### Overview

Three example scripts are provided:

- `vendor_phy.py` — a full example that demonstrates how to send a CTAP `CTAP_CONFIG` vendor subcommand and includes PIN-based authentication (pinUvAuthParam / PUAT). It can be used to read PHY options and to set a single PHY field (e.g. LED GPIO).
- `get_phy_opts.py` — a lightweight helper that reads PHY options via the vendor PHY_OPTS command and prints the decoded CBOR response. (Note: if the repository version does not include this file, use `vendor_phy.py` instead.)
- `get_memory.py` — a lightweight helper that reads memory statistics via the vendor MEMORY command and prints the decoded CBOR response.

### Prerequisites

- Python 3.8+
- Install dependencies:

```bash
python -m pip install fido2 cbor2
```

### How the scripts work

- Transport: scripts use the HID transport via `python-fido2` (the `CtapHidDevice` helper) and call CTAPHID CBOR (`CTAPHID_CBOR`) or the CTAP `CTAP_CONFIG` command depending on the implementation.
- Payload: vendor commands are encoded as CBOR maps. The firmware in this repo expects the vendor-subcommand layout inside a CTAP `CTAP_CONFIG` or a vendor-CBOR message: top-level map keys include `1` (subcommand), `2` (sub-parameters map), `3` (pinUvAuthProtocol) and `4` (pinUvAuthParam) when authentication is required.
- Authentication (PUAT): when a vendor operation requires authorization, the script performs these steps:
  1. Obtain a pin token using the `ClientPin` helper: `get_pin_token(pin, permissions)`.
  2. Construct the `verify_payload` (32 bytes of 0xFF, the `CTAP_CONFIG` byte, the vendor subcommand, and the raw sub-parameter bytes) and compute an HMAC-SHA256 with the pin token.
  3. Truncate the HMAC to 16 bytes for protocol 1 and include it as `pinUvAuthParam` (map key `4`) plus the `pinUvAuthProtocol` (map key `3`).

### Quick usage

Examples (with `vendor_phy.py` which handles PIN):

- Read PHY options (prompt for PIN interactively):

```bash
python tools/vendor_phy.py --interactive-pin --action read-opts
```

- Read PHY options (provide PIN on command line):

```bash
python tools/vendor_phy.py --pin 12345678 --action read-opts
```

- Set LED GPIO to 5 (requires PIN):

```bash
python tools/vendor_phy.py --pin 12345678 --action set-led-gpio --set-led-gpio 5
```

If you prefer minimal helpers and the repository contains `get_phy_opts.py` and `get_memory.py`, run them like this:

```bash
python tools/get_phy_opts.py
python tools/get_memory.py
```

**Notes and troubleshooting**

- Browser-based WebAuthn will not let you directly issue these vendor commands. To use the scripts from a web UI, run a small local native helper (like these scripts) that exposes a local HTTP API the web app can call.
- If a command is rejected with a CBOR error indicating missing authentication, obtain the PIN and retry. Use `--interactive-pin` if you do not want to put the PIN on the command line.
- Some vendor commands expect different sub-parameter formats (integers vs byte strings). Consult `src/fido/cbor_config.c` and `src/fido/cbor_vendor.c` for firmware-side expectations.
- If no HID device is found, ensure the authenticator is connected as a USB device and not being grabbed by another process (browser, PC/SC middleware, etc.).

### Extending the scripts

- Add more vendorCommandId constants (VID/PID, brightness, opts) in the scripts to implement other operations.
- Add a confirmation/readback step: after writing a PHY field, call a read vendor command (if available) to verify persistence.


## CBOR Command IDs and where to find them

This project uses CBOR-encoded CTAP/CTAP2 messages and several vendor-defined
command identifiers. Here is how to locate and understand those command IDs:

- In-repo definitions:
  - Core CTAP/CBOR values and vendor command constants are defined in
    `src/fido/ctap.h`. For example, `CTAP_CONFIG_PHY_LED_GPIO` and
    `CTAP_CONFIG_PHY_BTNESS` are declared there.
  - The firmware handlers for CTAP `config` and vendor CBOR commands live in
    `src/fido/cbor_config.c` and `src/fido/cbor_vendor.c` — these files show
    how each `vendorCommandId` is interpreted, which parameters are expected,
    and whether authentication (pinUvAuthParam / PUAT) is required.
  - The CTAP CBOR dispatcher is in `src/fido/cbor.c`; it shows how top-level
    CTAP commands are routed to the correct handler.

- How to search the repo for a command or handler:
  - Use a grep-like search for the constant name (e.g. `CTAP_CONFIG_PHY_LED_GPIO`) or for `vendorCommandId` usage:
    ```bash
    grep -R "CTAP_CONFIG_PHY_LED_GPIO\|vendorCommandId" -n src | sed -n '1,200p'
    ```

- External references and further reading:
  - The CTAP and WebAuthn specifications (FIDO2):
    - CTAP 2.1 spec (IETF / FIDO Alliance) — defines CTAP messages and CBOR formats.
    - WebAuthn specification — for how WebAuthn/CTAP interact on the client side.
  - CBOR and COSE docs:
    - RFC 7049 / RFC 8949 (CBOR) and COSE (RFC 8152) for encoding details.
  - python-fido2 documentation (https://github.com/Yubico/python-fido2):
    - Shows how to craft CTAP/CBOR calls from Python (`CtapHidDevice`, `ClientPin`).
  - The repository `tests/` folder contains examples that use `python-fido2`
    (see `tests/conftest.py` and many `tests/pico-fido/*.py` files) and can
    serve as practical examples of building CBOR payloads and authenticating
    with PIN tokens.


## APDU tools: reading/writing `EF_PHY`

Two small PC/SC-based utilities (APDU/CCID) allow reading and modifying the
`EF_PHY` blob stored in flash: `read_phy_apdu.py` and `write_phy_apdu.py`.

### Dependencies

- `pyscard` (package `python3-pyscard` or `pyscard`) and a running PC/SC
  daemon (`pcscd`). On Debian/Ubuntu you can install them with:

```bash
sudo apt update
sudo apt install -y pcscd python3-pyscard
sudo systemctl start pcscd
```

### `read_phy_apdu.py`

- Selects the firmware "rescue" AID and issues the APDU to read `PHY`
  (CLA=`0x80`, INS=`0x1E`, P1=`0x01`).
- Parses the returned serialized TLV blob and prints fields such as
  `led_gpio`, `led_brightness`, `led_driver`, `PHY_OPTS` (with known flag
  decoding), and `VID/PID` if present.
- Example:

```bash
python3 tools/read_phy_apdu.py
```

### `write_phy_apdu.py`

- Sends an APDU WRITE (CLA=`0x80`, INS=`0x1C`, P1=`0x01`) with a minimal TLV
  payload to update a single `phy_data` field. The firmware accepts partial
  TLVs and updates only the provided fields.
- Supported parameters: `led_gpio`, `led_brightness`, `led_driver`, `opts`,
  `vidpid`.
- Convenience option `--key-type <name>` maps a named key type to a
  VID:PID pair (mapping taken from `pico-keys-sdk/pico_keys_sdk_import.cmake`).
  Available types include: `NitroHSM`, `NitroFIDO2`, `NitroStart`, `NitroPro`,
  `Nitro3`, `Yubikey5`, `YubikeyNeo`, `YubiHSM`, `Gnuk`, `GnuPG`.
- Examples:

```bash
# from the repository root
python3 tools/write_phy_apdu.py --param led_brightness --value 4
python3 tools/write_phy_apdu.py --key-type Yubikey5
```

### Precautions

- CCID access may be held by other programs (browsers, PC/SC middleware).
  Close applications that may claim the device before using these scripts.
- `write_phy_apdu.py` modifies the persistent configuration (`EF_PHY`). Make
  a backup (read/dump) before writing if you need to preserve current values.
- If you prefer to perform changes over HID/CTAP (with proper PIN/PUAT
  authentication), use `tools/vendor_phy.py` which demonstrates CTAP/PIN flows.

### Verification

- After a write with `write_phy_apdu.py`, verify persistence with:

```bash
python3 tools/read_phy_apdu.py
```

If you want, I can add a `--list-key-types` option to `write_phy_apdu.py` and a
dedicated table in this README listing each key type and its VID/PID. Tell me
if you want that added.

## Adding custom vendor commands (example: LCD messages)

You can extend the firmware with custom vendor commands (for example, to
display text on an LCD instead of using LED blink codes). Below is a practical
guide and recommendations.

1) Overview — what to change
  - Define a new command ID in `src/fido/ctap.h` (e.g. `CTAP_CONFIG_PHY_LCD_MSG`).
  - Implement the handler in `src/fido/cbor_config.c` (for CTAP_CONFIG vendor
    pattern) or in `src/fido/cbor_vendor.c` (for the vendor-first byte pattern).
  - Add a small driver in `pico-keys-sdk/src/` to talk to the LCD (I2C/SPI),
    exposing an API such as `lcd_print(const char *s)` and `lcd_clear()`.
  - If the message must survive reboot, persist it using the EF file API
    (`file_new()`, `file_put_data()`) — either add a dedicated EF (e.g. `EF_LCD_MSG`)
    or reuse an existing appropriate EF.

2) Example handler flow (high level)
  - Parse CBOR vendor parameters (text, bytes or ints) in the handler.
  - Optionally require authentication: verify `pinUvAuthParam` and `paut.permissions`
    (use the same checks as other sensitive handlers in `cbor_config.c`).
  - Call your LCD driver API to update the display.
  - Persist the string to flash if required and call `low_flash_available()`.
  - Return a CBOR response with success or an appropriate CTAP2 error.

3) Example CBOR map (client side)
  - Top-level CTAP_CONFIG vendor map:
    ```py
    # pseudo-Python: vendor subcommand with text parameter
    top = {
      1: 0xFF,                    # subcommand == vendor
      2: {1: CTAP_CONFIG_PHY_LCD_MSG, 2: b"Hello, world!"},
      3: pinProtocol,             # if authenticated
      4: pinUvAuthParam           # if authenticated
    }
    ```

4) Security and access control
  - Protect sensitive operations with PUAT (pinUvAuthParam). Use
    `ClientPin.get_pin_token()` to obtain the pin token and compute the
    `pinUvAuthParam` as shown in `tools/vendor_phy.py`.
  - Check permissions server-side in the handler (e.g. `paut.permissions & CTAP_PERMISSION_ACFG`).

5) Naming and ID allocation rules (recommended)
  - Use the vendor/experimental range and pick clearly namespaced IDs. There
    is no global registry for firmware vendorCommandId values in this project,
    so follow an internal convention and document new IDs in `src/fido/ctap.h`.
  - Recommended format:
    - Use descriptive macro names with a `CTAP_CONFIG_PHY_` or `CTAP_VENDOR_`
      prefix, e.g. `CTAP_CONFIG_PHY_LCD_MSG`.
    - Use 64-bit numeric constants for vendorCommandId values (as the repo
      already does). Choose a value containing a project-specific prefix in
      the high bits to avoid accidental collisions with other vendors.
      Example pattern (not enforced by the spec): `0xVVVVVVVVXXXXXXXX` where
      `VVVVVVVV` is a small vendor/project identifier and `XXXXXXXX` is an
      operation-specific suffix.
  - Always add a comment in `ctap.h` documenting the purpose, parameter
    format (text/bytes/int) and whether PUAT is required.
  - If you plan to publish multiple devices or collaborate across teams,
    maintain a single `COMMAND_IDS.md` (or a section in `ctap.h`) listing
    allocated IDs and owners to prevent collisions.

6) Testing & tooling
  - Add tests under `tests/` that exercise the new CBOR handler using
    `python-fido2` (look at existing tests in `tests/pico-fido/` for examples).
  - Add a `tools/` script (like `vendor_phy.py`) for manual testing and
    document the sample CBOR in `tools/README.md`.

If you want, I can generate a minimal example patch that:
  - declares `CTAP_CONFIG_PHY_LCD_MSG` in `src/fido/ctap.h`,
  - adds a simple handler stub in `src/fido/cbor_config.c` that logs/returns
    the received text, and
  - adds a `tools/` client example that sends a test payload (PUAT optional).

