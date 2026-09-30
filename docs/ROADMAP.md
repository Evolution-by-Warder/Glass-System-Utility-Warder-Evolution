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

## 13.25-w6 test candidate — 2026-09-30

This candidate moves release checks and installation work off the Enigma2 GUI thread, tightens release asset/IPK identity checks, avoids repository-wide package queries in the package screen, and reports temperature interfaces separately from valid readings. It also reads process command lines from `/proc` without displaying full arguments. Static/build checks do not establish receiver runtime PASS; await the GigaBlue Quad 4K Pro test.
