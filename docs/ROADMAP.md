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


### 13.29-w10 authoritative CI artifact — 2026-09-30

Authoritative build commit: `d9510b25d9b9fba42ae4c3cba41b35bdb09be476`.
GitHub Actions run: `36752018129` — PASS.
Artifact: `enigma2-plugin-glasssysutil_13.29-w10_all.ipk`.
Size: 19,716 bytes.
SHA-256: `c1ca485b2ceb0709df41ca2cbfcaf7ee7be82654a0d1268741ae5bc1991e6262`.

The downloaded CI artifact was independently inspected after the workflow completed: deterministic ar member order is correct, package identity is `enigma2-plugin-glasssysutil`, package version is `13.29-w10`, and the embedded SHA-256 sidecar matches the independently calculated digest.

This is the receiver-test candidate only. Do not publish `v13.29-w10` until the real receiver checklist passes.


### 13.29-w10 real receiver validation — GigaBlue Quad 4K Pro — 2026-09-30

Receiver environment: GigaBlue Quad 4K Pro, OpenATV 8.0 beta/current, Python 3.14.

REAL RECEIVER PASS:
- package installation and plugin startup;
- Health Check: memory, storage, eth0, gateway, DNS, Enigma2 process, live temperature, CAM and tuner capability detection;
- Time & Synchronization: local/UTC time and running chronyd detected;
- Tuner Information: Enigma2 NIM sockets, DVB-S2X FBC frontends, /proc/stb/frontend, /sys/class/dvb and DVB adapters detected;
- Diagnostic Support Bundle: local tar.gz created successfully in /tmp;
- Active CAM / OSCam Monitor: oscam-uni detected with PID/runtime/memory and OSCam runtime/config/WebIF metadata;
- CAM Monitor Refresh: runtime refreshed without GUI freeze;
- CAM / OSCam Details: opens and scrolls correctly;
- Restart CAM: confirmation showed the discovered image-provided path /etc/init.d/softcam.oscam-uni; restart completed asynchronously; old PID 2898 changed to PID 8203; GSU verified the restarted CAM; process runtime reset; decrypted TV picture returned; no Enigma2 crash or GUI freeze.

REAL UI REVIEW:
- CAM Monitor action labels are currently white. Before release, restore conventional key colors: Close=red, Restart CAM=green, Refresh=yellow, Details=blue.
- Tuner diagnostics are functionally correct but deliberately technical; a future UX pass may add a concise human-readable summary while retaining raw technical details.

Release status: HOLD for the CAM Monitor key-color UI correction and one final receiver smoke test. Do not publish the current candidate as v13.29-w10.


### 13.29-w10 final UI smoke validation — GigaBlue Quad 4K Pro — 2026-09-30

REAL RECEIVER PASS after CAM Monitor UI correction:
- monitor opens normally with active oscam-uni;
- conventional action colors confirmed on receiver: Close red, Restart CAM green, Refresh yellow, Details blue;
- no regression observed in CAM runtime display.

The previously recorded CAM restart E2E PASS remains valid because the follow-up candidate changes only the action-label presentation. The 13.29-w10 feature set is now receiver-approved for release preparation.


### 13.29-w10 live OSCam monitor extension

The receiver-approved CAM monitor is being extended toward the useful OSCamInfo-style workflow without copying its UI or exposing credentials:
- local OSCam WebIF status API is queried only through loopback and only when WebIF authentication is not configured;
- GSU never reads or sends WebIF credentials for the live monitor;
- nested OSCam JSON status layouts are normalized defensively and bounded to 32 rows;
- useful diagnostic fields include reader/user identity, type, protocol, LAN/local address and port, srvid/CAID/PROVID, last channel, status, ECM time and idle time when exposed;
- live rows are integrated into the existing single CAM monitor and Details screen rather than adding menu clutter;
- if live API access is unavailable or authenticated, the existing process/runtime/config diagnostics remain functional.

Real receiver validation is required before this extension can be included in the w10 release checkpoint.


### Visual OSCam monitor implementation checkpoint

The live OSCam experiment has been promoted from raw/text diagnostics to a TV-oriented monitor:
- structured client/reader rows are separated from raw API payloads;
- nested scalar fields are normalized for differing OSCam API layouts;
- table presents Reader/User, Address, Port, Protocol, srvid:caid@provid, Channel, ECM, Idle and Status;
- raw Python/JSON structures are never rendered to the user;
- monitor refreshes live data every 5 seconds while open and stops its timer on close;
- manual Refresh remains available and row selection is preserved across refreshes;
- Details retains deeper runtime/config diagnostics;
- restart remains the previously receiver-verified image-provided service action.

Real receiver validation remains required for final field mapping and visual acceptance before v13.29-w10 release.


### OSCam monitor batch refinement — pre-receiver candidate

A coherent visual-monitor batch is now complete:
- raw API/dictionary output is excluded from the main screen;
- missing values render as clean empty cells rather than placeholder punctuation;
- nested OSCam field aliases are normalized for address, port, protocol, service identifiers, channel and timing;
- ECM timing and idle values are normalized to human-readable units;
- rows receive compact semantic role markers (reader/client/server/WebIF/local where detectable);
- status text is normalized for fast visual scanning;
- widescreen 1500x760 layout provides more room for the live table;
- visual hierarchy separates summary, live status, column header and table;
- five-second auto-refresh remains bounded, stops on close, preserves selection and is guarded against re-entry;
- safe restart and deeper Details behavior are unchanged.

CI is green for the implementation commits. Next gate is one real-receiver visual/data validation; no release should be published before that check.


### CURRENT recovery checkpoint — 2026-09-30 before maintainer offline

Authoritative production branch: `warder-master-production`.
CURRENT recovery commit: this documentation commit; source state immediately below is the last tested-by-CI implementation state.

Current product identity remains `13.29-w10`; **do not publish v13.29-w10 yet**.

OSCam monitor continuity:
- earlier receiver tests proved active `oscam-uni` detection, Refresh, Details and safe restart E2E; restart changed PID and recovered TV without GUI crash;
- conventional red/green/yellow/blue action-label colors were receiver-approved;
- the first live-API experiment proved the receiver's local OSCam API is reachable and exposes five live client/reader records, but raw/text presentation was rejected as unusable;
- current implementation replaces raw presentation with a bounded widescreen table, nested-field normalization, clean empty cells, role/status presentation, normalized ECM/idle values, five-second refresh, preserved row selection and refresh re-entry guard;
- no WebIF password is read or sent; authenticated WebIF falls back to existing safe diagnostics;
- raw Python/JSON structures must never be rendered in the user-facing monitor.

Latest implementation commit before this recovery record:
`29b2893b42e8ddf16987071acc6849445e25d8be` — refresh re-entry guard.
Its GitHub Actions build run `36761827898` is PASS.

Next action after resume:
1. build/test from the current production HEAD if documentation-only commits changed HEAD;
2. provide one coherent receiver candidate, not incremental IPKs;
3. validate the visual table and real field mapping on GigaBlue Quad 4K Pro;
4. refine only from observed receiver data;
5. publish `v13.29-w10` only after this visual/live OSCam gate is REAL RECEIVER PASS.

Do not roll back to the raw live-status experiment and do not create a new release/version merely for testing.


### OSCam monitor continuation after CURRENT checkpoint

Post-checkpoint hardening completed:
- a privacy-safe OSCam API schema diagnostic records **field names/structure only**, never values;
- credential-like branches (password/passwd/pwd/token/secret/key/boxkey/deskey/rsakey/user/username/account) are excluded from schema diagnostics;
- the safe schema is available only inside CAM/OSCam Details to help map receiver-specific OSCam JSON layouts without asking the maintainer to expose credentials or raw payloads;
- the live refresh re-entry flag is now reset in a `finally` block so an unexpected parser/UI exception cannot permanently freeze future refreshes.

Relevant implementation commits:
- `70cd8b5ff2482cdff7114dec28b10f38aea8f553` safe schema collector;
- `d66fdf697f27ca097e03607aa668268e30ee8838` Details integration;
- `97553505f69554dcf22ebc483d84c0be75c267db` exception-safe refresh lifecycle.

All source-triggered GitHub Actions runs for this batch are PASS. The release gate remains unchanged: one coherent receiver candidate must validate actual visual/live field mapping before v13.29-w10 publication.


### 2026-10-01 coherent w10 receiver candidate

The OSCam live monitor is ready for the next single receiver validation batch.

Additional hardening:
- periodic five-second OSCam WebIF fetch no longer performs network I/O on the Enigma2 GUI thread;
- only one live fetch worker may run at a time;
- worker completion updates the table on the Enigma2 timer path;
- closing the monitor stops periodic refresh and prevents an outstanding worker from updating a closed screen;
- manual refresh, Details and safe CAM restart behavior remain available.

Validated source commit: `4f36bfdb9ff598751fce55e2db24381a4590886b`.
GitHub Actions run: `36822113432` — PASS.
CI artifact IPK: `enigma2-plugin-glasssysutil_13.29-w10_all.ipk`, 23,616 bytes,
SHA-256 `400be4cb1ab7376becb6efa1b97ac3936bbbbd1d3116f6d5a04b0c924e74c500`.

Receiver gate:
- confirm monitor opens without GUI stall;
- confirm table is visually useful and stable across automatic refresh;
- inspect which real fields populate;
- if important fields remain empty, use Details -> OSCam API schema (field names only) to guide mapping without exposing credentials or raw API values;
- do not publish v13.29-w10 until this gate passes.


### 2026-10-01 OSCam monitor pre-hardware completion batch

Further work completed without consuming additional receiver test cycles:
- support bundles now include the privacy-safe `oscam-api-schema.txt` when OSCam is active; it contains field names/shape only and passes through the existing bundle redaction path;
- live worker lifecycle now refuses work while the screen is closing and safely clears its running flag if thread creation itself fails;
- the live status line now reports mapping completeness (populated safe diagnostic fields / total fields and percentage), allowing receiver screenshots to quantify parser usefulness immediately without exposing additional values;
- all changes remain read-only except the already receiver-approved explicit CAM restart action.

Validated implementation commit: `610c527cacdadf601b4401ffdf3801148f9c114a`.
GitHub Actions run `36823001271`: PASS.
This supersedes the previous receiver candidate source while keeping version `13.29-w10` and the same release HOLD.


### 13.29-w10 OSCam monitor presentation checkpoint
- Live OSCam API data is rendered as a true fixed-column Enigma2 table rather than a space-padded terminal line.
- Address, port, protocol, service identity, channel, ECM, idle and status have independent fixed cells.
- WebIF/HTTP and empty localhost infrastructure rows are hidden from the primary TV table while remaining available to diagnostics.
- Missing reader/user names use neutral role labels (Reader, Client, EMU, DVBAPI); real API names always win.
- Refresh preserves selection, is centralized, remains non-blocking for periodic live updates, and screen close stops owned timers.
- Release remains HOLD until this presentation batch passes CI and one real-receiver Update smoke test.


### 13.30-w11 receiver update candidate
- 13.29-w10 remains the development checkpoint that established the live OSCam monitor.
- The polished fixed-column receiver UI is promoted to 13.30-w11 so an already-installed w10 development package can exercise the real in-plugin Update path.
- Includes fixed Enigma2 column layout, static skin binding cleanup, useful-row filtering, normalized OSCam aliases, duplicate suppression, row details, non-blocking refresh, selection preservation and guarded CAM restart lifecycle.
- Publication remains gated by exact-version source/control/postinst agreement, full tests, deterministic build and immutable release verification.
- Receiver acceptance: update discovery/install/restart plus one OSCam monitor visual/function smoke test.
