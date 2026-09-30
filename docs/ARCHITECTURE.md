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


## Capability discovery

Glass System Utility Warder Evolution detects capabilities from the running Linux/Enigma2 system before considering receiver-specific fallbacks.

- Do not branch on receiver brand/model when a standard runtime interface can be probed.
- Prefer Linux interfaces such as sysfs, procfs, process state, mounts and image-provided runtime files.
- Treat sysfs class entries as possible symlinks and enumerate/probe them explicitly where required.
- A missing interface means only that the current kernel/image does not expose that capability through a detected path; it does not prove the physical hardware lacks it.
- Vendor-specific handling is a fallback only when there is no reliable capability-based interface.
- Read-only discovery is preferred; state-changing operations remain separately gated and tested.


## Self-update channel

GSU uses the project's official public GitHub Releases as its update authority.

- At most one silent network check is started per Enigma2 GUI session, on a worker thread.
- Neither the automatic check nor the manual check blocks the Enigma2 GUI thread.
- If no newer release exists or the network is unavailable, startup is not interrupted.
- A newer version is offered to the user; installation is never performed without confirmation.
- Only the exact versioned `.ipk` asset hosted under this repository's official GitHub release-download path is accepted. Redirects are accepted only to HTTPS GitHub release-asset hosts, HTML responses are rejected, the IPK archive signature and metadata size are checked, and `opkg info` must report the expected package identity and release version.
- The downloaded package is installed through `opkg`; a GUI restart is requested after a successful update.
- A manual **Check for updates** action is also available from the plugin.
- Development commits are not treated as releases. Publishing a GitHub Release is the explicit act that makes a build available to installed receivers.
- A public GitHub Release is prepared only after a real receiver test and explicit user approval.
