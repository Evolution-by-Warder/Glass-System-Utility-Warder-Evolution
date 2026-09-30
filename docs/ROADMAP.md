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
