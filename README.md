# Glass System Utility Warder Evolution

Modern continuation and evolution of the Glass System Utility Enigma2 plugin.

## Project status

The current production development version is recorded in `src/GlassSysUtil/version`. Version 13.25-w6 is a test candidate; runtime status is not PASS until it is checked on a receiver.

This repository is a **standalone project**. It is not part of PiconHub Warder Evolution or FullHDGlass Warder Evolution.

## Direction

The project will progressively rebuild the useful ideas of the legacy Glass System Utility as a modern Enigma2 system, service and administration center while removing obsolete Python-version-specific bytecode and unsafe legacy assumptions.

Planned areas include system and hardware information, networking and server diagnostics, storage and device management, NFS/CIFS mounts, CAM/SRV management, OSCam information, scripts, services and processes, packages, logs and diagnostics, backup/restore, channel/tuner information, maintenance tools and GSU settings.

## Compatibility strategy

- normal Python 3 source code; no `plugin.py38o` / `plugin.py313o` style cores
- no Python 2.6/OE 1.6 fallback
- feature detection instead of hardcoded image assumptions
- dangerous write operations are migrated and tested separately
- autostart hooks return only after their components are safely ported

## Test build

Build a deterministic IPK from this checkout with `sh tools/build-ipk.sh`. The artifact and its SHA-256 file are written to `dist/`. GitHub Actions runs the same source/version/package checks on changes to the production branch. A test build is not a GitHub Release; installed receivers only receive updates from an explicitly published official Release.

## Credits

Glass System Utility is an existing project and its original authorship is respected. **Warder Evolution** identifies the modernization and continuation work; it does not claim authorship of the original GSU code.
