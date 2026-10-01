# GSU 13.20 -> Warder Evolution migration audit

Status: ACTIVE MIGRATION AUTHORITY
Date: 2026-10-01
Branch: warder-master-production

## Rule

The immutable GSU 13.20 package in Trezor is the content and visual baseline. Warder Evolution repairs and modernizes it; it does not place a generic diagnostics plugin beside it. Original authorship is preserved. Published releases remain immutable.

The GitHub connector can identify the binary Trezor artifact and its blob, but does not expose binary IPK payload bytes as UTF-8 source. Therefore byte-level package extraction is not claimed here. This audit records only functions/screens already evidenced by the preserved original package metadata and the supplied original GSU 13.20 receiver screens. Source-level parity must be checked whenever extracted legacy source is available; no undocumented legacy behavior may be invented.

## Original top-level contract and migration decision

| Original GSU 13.20 area | Warder decision | Modern engine / safety rule |
| --- | --- | --- |
| System Information | RESTORE as rich dashboard | system, memory, storage, temperature, process/service and protocol probes; read-only |
| Channel Information | RESTORE as rich dashboard | live Enigma2 service/frontend data + current CAM/ECM data; capability-first |
| CCcam Information | CONDITIONAL | show only when safely detected; no fabricated compatibility |
| OSCam Information | RESTORE / INTEGRATE | existing approved OSCam live backend; localhost WebIF only when safe; no secrets |
| Mbox Information | CONDITIONAL | only if detected and a safe modern data source exists |
| IPK/DEB and user scripts | REPAIR / GATE | package operations only with explicit user action; no legacy remote downloader revival |
| ECM Information | RESTORE / INTEGRATE | current-service + safe CAM/OSCam ECM engine |
| CAM/SRV Manager | PRIORITY RESTORE | original information hierarchy and coloured actions; capability-aware safe start/restart only |
| OSD ECM Information | REVIEW | preserve only if current Enigma2 API supports it cleanly |
| Swap management | REPAIR | inspect/report first; state changes explicit and guarded |
| Channel settings | REVIEW | preserve meaningful current Enigma2 operations only |
| Device manager | RESTORE | storage/device capability view; destructive actions excluded until separately validated |
| Automatic installations | DO NOT REVIVE BLINDLY | obsolete network installers are not inherited merely for parity |
| Crond management | CONDITIONAL | only when cron capability exists; explicit state-changing actions |
| Text editor | REVIEW | avoid duplicating image facilities unless it solves a real receiver need |
| Root password reset | SECURITY REVIEW | never silently reset credentials; only explicit safe image-supported flow |

## Original visual contract

Main screen keeps the recognizable GSU hierarchy rather than the current flat diagnostics list. Availability is visible before entering an item. A contextual description follows selection. Coloured keys have screen-local meaning. Rich screens group related live information instead of opening many raw text pages.

System Information restores the original dense dashboard concept: RAM/swap/root/storage, temperature/CPU state, process and dmesg/service information, and protocol/service indicators. Channel Information restores service/provider, ECM, signal, bitrate where supported, transponder and PID/CA data, plus channel/provider/satellite/CA visual areas where assets are available.

CAM/SRV Manager is a first-class screen, not a renamed OSCam table. It restores active/detected CAM/SRV state, current service/provider/satellite/CA context, live ECM details, available CAIDs and safe actions. The existing Warder OSCam table/data extraction remains the engine and can be embedded or opened as detailed live-client information.

## Modern Warder facilities to fold into the original structure

Health Check, Service Dashboard, Network Health, Network Mount Doctor, Storage Health, Enigma2 Runtime Health, tuner/temperature/system/network/storage/memory/service/mount/log diagnostics, diagnostic bundle and updater remain available, but are consolidated under original-style dashboards and a diagnostics/tools area rather than dominating the top-level menu.

## Migration gates

1. Read-only information screens may move first.
2. CAM restart/start actions require capability detection and receiver verification.
3. Package, swap, cron, device and credential changes remain gated until separately audited.
4. No shell killall CAM fallback.
5. No credential display or secret collection in diagnostics.
6. Missing capability disables/degrades a function; vendor-name branching is fallback only.
7. A migrated function is not REAL PASS until exercised on the GigaBlue Quad 4K Pro / current OpenATV.


## Authoritative package extraction — 2026-10-01

The exact original `glasssysutil_13.20.ipk` was supplied and verified locally before this checkpoint.

- SHA-256: `81aea6eb25b5ed519e904af87a3d7bece5d32ae6886a1690dac8ab47306fe3f7` (matches the immutable Trezor original).
- The package contains the original SD/FHD/UHD skin modules and complete original image assets; these are now the visual authority and must not be redesigned.
- The plugin payload contains compiled implementations for Python 2.6, 3.8, 3.9, 3.10, 3.11, 3.12 and 3.13. The Python 3.13 payload is a valid CPython 3.13 bytecode module whose embedded source metadata reports `plugin.py` size 455820 bytes.
- The original postinst selects a version-specific bytecode file and has no Python 3.14 branch. This is the concrete compatibility blocker for current OpenATV/Python 3.14.
- The original source `plugin.py` is not shipped in the IPK. Therefore the Python 3.14 port must be source-recovered/reconstructed from the authoritative 3.13 implementation while preserving original classes, functions, skins, assets and behavior. It must not be replaced by the post-w17 Warder dashboard design.

Recovered top-level implementation inventory includes the original `SysUtilMngMain`, `GlassSysInfoBrowser`, `channelInfoCenter`, CCcam/OSCam/Mbox information screens, `univCamMng`, IPK/script/TAR centers, ECM/OSD ECM, swap/device/partition management, auto-install management, cron management, text editor and configuration/browser screens. This inventory supersedes screenshot-only inference.
