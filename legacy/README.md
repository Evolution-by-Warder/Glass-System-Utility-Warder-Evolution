# Legacy / original GSU authority

The immutable original Glass System Utility 13.20 package is preserved in the private Trezor at `archives/glasssysutil/glasssysutil_13.20.ipk`. It is the architectural and visual baseline for Glass System Utility - Warder Evolution and must never be modified in place.

Migration policy:

1. Inspect the original 13.20 implementation screen-by-screen and function-by-function.
2. Preserve its recognizable information architecture, dashboard character, navigation model, contextual help, status indicators and coloured-key interaction where still appropriate.
3. Validate each historical function against current Enigma2/OpenATV behavior. Repair or replace obsolete internals; never revive unsafe mechanisms merely for parity.
4. Integrate Warder Evolution capability detection, diagnostics, safe CAM/OSCam engine, updater and localization into the original GSU structure instead of building a second generic utility beside it.
5. Consolidate duplicate diagnostics into richer original-style System Information, Channel Information and CAM/SRV screens.
6. Keep published releases immutable and require real-receiver validation before a migrated state-changing function is considered production proven.

The original package remains reference authority. Active production code lives under `src/GlassSysUtil`; migrated code must be auditable and must not silently copy unsafe legacy behavior.
