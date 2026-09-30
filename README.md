# Glass System Utility Warder Evolution

Modern continuation and evolution of the Glass System Utility Enigma2 plugin.

## Project status

The current baseline is **13.21-w2**: a clean Python 3 source-core bootstrap confirmed on real Enigma2 hardware with Python 3.14.

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

## Credits

Glass System Utility is an existing project and its original authorship is respected. **Warder Evolution** identifies the modernization and continuation work; it does not claim authorship of the original GSU code.
