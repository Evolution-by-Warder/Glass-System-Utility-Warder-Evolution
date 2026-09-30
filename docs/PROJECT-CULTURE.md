# Warder Evolution Project Culture

Glass System Utility Warder Evolution follows the same governance discipline used across Warder Evolution projects while remaining a completely standalone project.

## Authority model

- **Trezor original:** `archives/glasssysutil/glasssysutil_13.20.ipk` is the immutable original/GOLDEN SOURCE.
- **Original identity:** 3,611,958 bytes; SHA-256 `81aea6eb25b5ed519e904af87a3d7bece5d32ae6886a1690dac8ab47306fe3f7`; Git blob `2b5f5e4985f86ef70e7577a720a50a6564d3281f`.
- **Modern project:** all development belongs only in `Evolution-by-Warder/Glass-System-Utility-Warder-Evolution`.
- **Production work:** `warder-master-production` is the working production line.
- **main:** stable baseline; production work is not casually merged, rebased, or force-pushed into it.

## Culture

Every preserved artifact must have one clear purpose. Authority must be recoverable from repository documentation without relying on chat history.

Use:
- one current production state
- one authoritative approval/continuity record when such a record becomes necessary
- one CURRENT recovery checkpoint
- MILESTONE checkpoints only for genuinely significant states
- reproducible build inputs and clearly identified release artifacts

Avoid:
- duplicate originals
- ambiguous `final-final` artifacts
- unnecessary experimental version clutter
- obsolete CURRENT checkpoints
- undocumented archives, caches and logs

## Project separation

The shared element across PiconHub Warder Evolution, FullHDGlass17 Warder Evolution and Glass System Utility Warder Evolution is **governance culture only**.

Never mix their code, repository history, branches, checkpoints, release artifacts or project-specific documentation.

## Original authorship

The legacy Glass System Utility remains the work of its original authors. Warder Evolution identifies modernization and continuation work only.
