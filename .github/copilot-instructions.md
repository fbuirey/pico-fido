## Objectif
Fournir à un agent IA (Copilot) les informations essentielles pour être immédiatement productif dans ce dépôt "pico-fido" (firmwares pour RP2040 / RP2350 / ESP32-S3).

## Vue d'ensemble (big picture)
- **But :** firmware FIDO/WebAuthn pour microcontrôleurs (RP2040 family & ESP32-S3). Le projet contient du code cible « Pico » (`RP2040/RP2350`) et des builds pour `ESP32-S3`.
- **Architecture :** boot + tinyusb USB stack + gestion de fichiers/flash (OTP, résident keys) + apps (APDU handlers). Les composants clefs sont répartis entre `pico-keys-sdk/` (SDK partagé) et `src/` (implémentation FIDO spécifique).
- **Pourquoi cette séparation :** `pico-keys-sdk` est un SDK réutilisable (USB, flash-low-level, leds, crypto wrappers), `src/` contient l'intégration applicative et la logique FIDO.

## Dossiers et fichiers clés (à consulter en priorité)
- `CMakeLists.txt` : configuration de build multi-target (RP2040 / ESP).
- `build_pico_fido.sh` : script de packaging pour UF2 (RP2040). Exemple d'usage rapide pour builds release.
- `pico-keys-sdk/src/main.c` : point d'entrée principal (fonctions `do_flash()`, `low_flash_init()`, `scan_flash()` ; sections conditionnelles `PICO_PLATFORM` / `ESP_PLATFORM`).
- `pico-keys-sdk/src/fs/*` : interactions bas-niveau avec la flash et structure des fichiers/OTP.
- `pico-keys-sdk/src/usb/*` : configuration TinyUSB, descriptors et gestion CCID/HID.
- `pico-keys-sdk/mbedtls/` : crypto (lib incluse); préférez ces wrappers plutôt que d'ajouter d'autres bibliothèques crypto.
- `tests/` : suite PyTest (basée sur `python-fido2`) + helpers Docker (`run-test-in-docker.sh`, `build-in-docker.sh`).
- `sdkconfig` & `pico-keys-sdk/config/esp32/` : configuration ESP-IDF / partitions pour ESP32-S3.

## Build, flash et test (exemples concrets)
- Build rapide (RP2040) — minimal :
  - `mkdir build && cd build`
  - `PICO_SDK_PATH=/path/to/pico-sdk cmake .. -DPICO_BOARD=board_type -DUSB_VID=0xFEFF -DUSB_PID=0xFCFD`
  - `make` (ou `make -j$(nproc)`).
- Packaging release UF2 (script fourni) :
  - `./build_pico_fido.sh` (génère `release/pico_fido_<board>-<ver>.uf2`).
- Flash RP2040 : copier le `*.uf2` sur le stockage USB du Pico en mode BOOTSEL.
- Build / flash ESP32-S3 (prérequis : ESP-IDF) : le dépôt contient `sdkconfig` et composants. Utilisez l'outillage ESP-IDF classique (`idf.py build` / `idf.py -p <PORT> flash monitor`) ou l'utilitaire indiqué dans `README.md` (lien vers ESP32 Flasher). Vérifiez `CONFIG_IDF_TARGET` dans `sdkconfig`.
- Tests unitaires/integration : depuis la racine : `pytest` ou `pytest -k <pattern>`. Pour environnement isolé, utiliser `./tests/run-test-in-docker.sh`.

## Conventions de code et patterns observés
- **Cible multi-plateforme** : code fortement conditionné par `#ifdef PICO_PLATFORM`, `#ifdef ESP_PLATFORM`, `#ifdef ENABLE_EMULATION`. Ajoutez les nouvelles fonctionnalités en gardant ces branches séparées.
- **Séparation HW/logic** : matériel (LED, bouton, flash low-level) est encapsulé sous `pico-keys-sdk/src/{led,fs,usb}`. Pour modifier le comportement matériel, éditez ces modules, pas `src/main.c` directement.
- **USB descriptors** : personnalisations dans `pico-keys-sdk/src/usb/usb_descriptors.c` — utile pour ajouter interfaces CCID/HID ou modifier strings (voir comment `tusb_cfg.string_descriptor[]` est construit dans `main.c`).
- **Flash-safe operations** : fonctions critiques (`do_flash`, `low_flash_init`, `low_flash_init_core1`, `scan_flash`) manipulent directement la flash/OTP — modifier uniquement si vous comprenez implications (interrupts, cache, IRAM).

## Ajout d'une fonctionnalité (exemple rapide)
- Pour exposer une nouvelle commande USB :
  1. Ajouter le handler dans `pico-keys-sdk/src/usb/*` (ou `ccid`/`hid` selon le cas).
  2. Enregistrer l'app ou le handler via l'API d'apps (`register_app`, `select_app` dans `pico-keys-sdk/src/main.c`).
  3. Mettre à jour `pico_keys_sdk_import.cmake` si de nouveaux fichiers sources sont nécessaires.
  4. Tester localement en build/flash et exécution de `pytest` côté hôte si le test est de bout en bout.

## Débogage et recommandations pratiques
- Logs série (ESP) : utilisez `idf.py monitor` ou le moniteur série configuré dans `sdkconfig`.
- Pour RP2040, utilisez `printf` + LED blink states décrits dans `README.md` pour indicator states.
- Attention aux sections non-reentrantes et aux appels en flash-disabled (ex. `picok_get_bootsel_button`) — ces fonctions désactivent l'accès à la flash temporairement.

## Sécurité & responsabilités (notes importantes)
- Code manipule clés privées et OTP ; changements ici modifient la surface d'attaque. Éviter d'ajouter des dépendances crypto non auditées.
- RP2040 ne fournit pas le même niveau de sécurité hardware que les RP2350/ESP32-S3. Les commentaires dans `README.md` et `sdkconfig` documentent ces différences.

## Où regarder pour plus de contexte
- `pico-keys-sdk/src/` : logique SDK (USB, flash, led, fs, crypto wrappers).
- `src/fido/` : implémentation FIDO spécifique (attestations, CTAP handling).
- `tests/` : exemples de tests et environnement Docker pour reproduire CI-like runs.
- `build/` : artefacts et arguments de flash générés — utile pour comprendre les flags de construction actuels.

Si une section est incomplète ou si vous voulez que j'ajoute des exemples de commandes supplémentaires (par ex. `idf.py` exact pour ESP32-S3 sur votre machine), dites-moi quels environnements vous utilisez (local toolchain paths, USB port, board type). Je peux itérer. 
