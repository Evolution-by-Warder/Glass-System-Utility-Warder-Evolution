# Architecture

## Baseline

13.21-w2 replaces the legacy minor-version bytecode selector with a normal Python source core. Python itself owns bytecode caching.

## Principles

1. Preserve useful GSU behavior, not obsolete implementation details.
2. Detect capabilities at runtime rather than assuming one Enigma2 image or Python minor version.
3. Keep read-only diagnostics separate from state-changing administration.
4. Treat mounts, fstab, partitions, swap, CAM startup and autostart as safety-sensitive features.
5. Keep original authorship and Warder Evolution modernization credits unambiguous.

## Repository layout

- `src/GlassSysUtil/` — runtime plugin source
- `packaging/` — Enigma2 package metadata and maintainer scripts
- `tools/` — reproducible build helpers
- `docs/` — architecture, roadmap and testing policy
- `tests/` — host-side tests where practical
- `legacy/` — documentation/reference material only; never an active runtime core
