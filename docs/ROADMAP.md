# Roadmap

The confirmed 13.21-w2 bootstrap is the starting point.

Development proceeds from low-risk diagnostics to state-changing functions:

1. System, hardware, memory, storage and network diagnostics.
2. Server/connectivity diagnostics and service/process inspection.
3. Channel/tuner information and log/diagnostic export.
4. OSCam information and read-only CAM/SRV status.
5. Script/package administration and backup/restore.
6. NFS/CIFS and storage/device management.
7. CAM/SRV lifecycle management.
8. Carefully gated partition/swap/fstab operations where still justified.
9. Autostart integration only after dependent components are proven safe.

Legacy functionality is evaluated feature-by-feature; obsolete mechanisms are not restored merely for compatibility.


## 13.23-w4 receiver checkpoint — 2026-09-30

GigaBlue Quad 4K Pro / OpenATV / Python 3.14 runtime PASS: modern process discovery and OSCam process/config-dir detection verified on real hardware. Continue read-only migration without per-line approval; state-changing operations remain separately gated.

## 13.25-w6 real receiver checkpoint — 2026-09-30

Commit `fa31a924500639bfdd1e107d8b534141e1039f92`.

STATIC PASS and BUILD PASS were completed for the deterministic IPK. REAL RECEIVER PASS was then confirmed on GigaBlue Quad 4K Pro / OpenATV 8 / Python 3.14 across the requested w6 checklist: temperature discovery, Detected Capabilities, Hardware Identity, Services & Processes, OSCam, Package information, diagnostic scrolling, and manual update-check responsiveness. Temperature data was successfully read through the capability-driven interface; an observed runtime reading was 37 °C.

The end-to-end GitHub Release update path remains REVIEW because no public release had been published during this checkpoint. Release discovery, confirmation, download, verification, `opkg` installation and the automatic three-second GUI restart must be verified separately before that path is marked REAL RECEIVER PASS.

Test artifact: `enigma2-plugin-glasssysutil_13.25-w6_all.ipk`
SHA-256: `d72e961f794d620537617622488a8dbad03a2e3f22ae2924296a0bfb00409138`.


## 13.26-w7 update-path candidate — 2026-09-30

13.26-w7 is intentionally a minimal successor to the REAL RECEIVER PASS 13.25-w6 checkpoint. Its purpose is to validate the complete official GitHub Release self-update path from an installed w6 receiver without mixing unrelated feature changes into that test. Source/runtime behavior remains based on the tested w6 implementation; version/package metadata advance together to 13.26-w7. Publishing the public Release remains gated by explicit user approval.


## 13.27-w8 real receiver updater result

- RELEASE PUBLISHED PASS: official GitHub Release `v13.27-w8`, target `9bdb1e37a6d35755e5600634dea0500415dc29fc`.
- REAL RECEIVER UPDATE DISCOVERY PASS: 13.25-w6 detected 13.27-w8.
- DOWNLOAD / RELEASE VERIFICATION / OPKG INSTALL PASS on GigaBlue Quad 4K Pro, OpenATV 8, Python 3.14.
- Receiver verification after the event: `opkg status` reported `Version: 13.27-w8` and `Status: install ok installed`; the installed version file also contained `13.27-w8`.
- After Enigma2 restarted, About loaded Glass System Utility Warder Evolution 13.27-w8.
- POST-INSTALL UI COMPLETION FAIL/REVIEW: OpenATV still registered a software crash while the updater transitioned from the progress dialog to its completion/restart UI.
- Conclusion: the transport, verification and package-install path is proven; remaining work is isolated to modal-safe GUI completion/restart handling.
- The published w8 release remains immutable.

## 13.28-w9 updater completion candidate

- Candidate source HEAD: `eac32fa5ad39992ec9c4683c6d8646ac688f29f2`.

- Removes the post-install modal swap entirely.
- Reuses the already-open progress MessageBox for success/error status.
- Schedules the GUI restart independently after 3 seconds.
- Avoids opening `TryQuitMainloop` as a nested modal; uses its quit action directly with a `quitMainloop(3)` fallback.
- REAL RECEIVER status: REVIEW until update from installed 13.27-w8 is tested.


## 13.28-w9 real receiver result

- REAL RECEIVER PASS on GigaBlue Quad 4K Pro / OpenATV 8 / Python 3.14.
- Starting state: installed and loaded 13.27-w8.
- Update discovery PASS: updater offered 13.28-w9 and correctly reported installed 13.27-w8.
- Download / verification / installation progress PASS.
- Post-install completion PASS: no OpenATV software-problem dialog was observed.
- Automatic GUI restart PASS: receiver restarted cleanly before a third test screenshot could be captured.
- This closes the post-install modal-lifecycle blocker seen in w7 and w8.
- Release v13.28-w9 remains immutable.


## Post-w9 read-only development

With the self-update path proven on real hardware, development resumes at roadmap stage 3. Tuner diagnostics now use capability-based discovery across Enigma2's `/proc/bus/nim_sockets`, exposed frontend interfaces and Linux DVB device adapters. The implementation remains bounded and read-only and does not branch on receiver vendor/model.

Next in this stage: diagnostic export/support bundle design with explicit secret redaction before any state-changing administration is introduced.


## Modern user-needs review — 2026-09-30

Post-w9 development is not limited to reproducing the historical Glass System Utility feature set. Current Enigma2 user support patterns are used to guide new work while keeping GSU capability-driven and image-neutral.

Priority themes for future candidates:
- Health Check / Troubleshooter: one read-only overview of system, Enigma2 process, memory, storage, network, DNS/connectivity, mounts, tuners, temperatures, services and CAM status.
- Network and Mount Doctor: distinguish interface/link, addressing, gateway/DNS, server reachability, configured shares, active mounts, filesystem availability and recording-target problems.
- Storage Health: capacity, filesystem, mount state and available SMART/NVMe health information where the receiver exposes it.
- Enigma2 Runtime Health: process memory and uptime observations, crash/debug-log discovery and diagnostics useful for hangs or long-running resource growth.
- Time Health: detect available time-sync implementation and report clock/NTP/chrony state without assuming a particular image.
- Tuner / Signal Diagnostics: continue capability-based frontend discovery and expose useful signal/frontend state where supported.
- Support Bundle: local, user-initiated diagnostic archive with authentication secrets and cryptographic keys redacted. Useful diagnostic identifiers such as interface MAC addresses remain available. Nothing is uploaded automatically.
- Service Dashboard: read-only status for relevant services actually detected on the receiver rather than a fixed vendor list.
- Existing image facilities should be diagnosed or integrated where practical instead of needlessly duplicating mature backup, flashing or package-management functionality.

Design rule: show what helps diagnosis, protect what grants access, and never transmit diagnostic data without an explicit user action.

REAL RECEIVER validation remains mandatory before state-changing administration is promoted as production-ready.


## 13.29-w10 development candidate

The w10 line is the first post-w9 feature candidate. It is intentionally unreleased while receiver validation is pending.

Included so far:
- expanded capability-based tuner diagnostics;
- local diagnostic support bundle with bounded text-log collection and privacy filtering;
- practical privacy policy: authentication secrets and stable private identifiers are filtered while useful interface identifiers such as MAC addresses remain visible;
- first read-only GSU Health Check covering memory, mounted physical storage, network link/configuration, Enigma2 process presence, exposed temperatures, network mounts, detected CAM processes and tuner interfaces;
- modern user-needs roadmap based on recurring Enigma2 support themes rather than historical feature parity alone.

Status: STATIC/CI validation in progress; REAL RECEIVER REVIEW required before release.


### CAM / OSCam monitor consolidation

- Consolidated separate OSCam status/WebIF/runtime top-level entries into one focused Active CAM / OSCam Monitor.
- Detects the actually running CAM process rather than assuming a receiver vendor.
- Shows process identity, PID, runtime and memory alongside existing OSCam runtime/WebIF diagnostics.
- Restart is deliberately state-changing and therefore requires explicit confirmation.
- Restart uses only a discovered image-provided init/service path; there is no blind process-kill fallback.
- A successful restart command is followed by active-CAM re-detection before success is reported.
- Passwords, tokens and cryptographic keys remain excluded; ordinary diagnostic network identifiers are not needlessly hidden.
- Receiver validation is required before 13.29-w10 can be released.


### 13.29-w10 pre-receiver candidate checkpoint — 2026-09-30

Production source and regression suite are green at commit `1e522dfd479184b4c81c9053c2076204f04318bf`.

The candidate contains the post-w9 read-only diagnostics block (expanded tuner discovery, Time & Synchronization, Health Check and privacy-safe local Diagnostic Support Bundle) plus the consolidated Active CAM / OSCam Monitor. The monitor detects the running CAM, exposes runtime diagnostics, provides Refresh and Details actions, and offers a confirmation-gated restart using only a discovered image-provided service path. There is no generic `killall` fallback. CAM restart work runs outside the Enigma2 UI thread and re-detects the CAM before reporting success.

STATIC/CI: PASS.
REAL RECEIVER: REVIEW REQUIRED.
Release: NOT PUBLISHED. The immutable 13.28-w9 release remains the current public release until the w10 receiver checklist passes.
