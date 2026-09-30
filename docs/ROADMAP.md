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
