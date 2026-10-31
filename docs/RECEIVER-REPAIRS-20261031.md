# GSU receiver repairs — 31 October 2026

Target package: **13.40-r95**, with the existing native package identity and short filename.

The owner supplied the exact original 13.20 IPK, SHA256 `81aea6eb25b5ed519e904af87a3d7bece5d32ae6886a1690dac8ab47306fe3f7`. Its postinst deletes shipped default files and unused Python variants but leaves their opkg ownership entries. A real opkg 0.10.0/libsolv 0.7.40 isolated test reproduced 12 obsolete-file errors before the fix and zero after it. Both cases reached installed state, explaining why the original screenshots had errors but the new GSU still opened.

The new preinst admits only the exact known postinst and ordinary ownership list, rejects unexpected removal hooks, and recreates only missing, allowlisted, still-owned paths. Existing files and symbolic links are preserved. Both upgrade and renamed-install invocations work; preparation never depends on a nested query to an active opkg process. No status database is edited, and receiver commands need no force options.

The new installed-files manifest hashes all packaged Python modules and the runtime version. Postinst verifies files before its configuration message; the updater executes the newly installed verifier and checks the exact final package/version/fully-installed state before reporting success or restarting GUI. A verification failure follows the existing error/recovery flow.

The About view now shows four short, separated, localized history entries. Full historical source remains available; operational output is not truncated.

The owner confirmed that the previous r94 starts after direct 13.20 replacement. Physical receiver retest of r95 remains pending. The simulation uses the original hook/inventory, minimal old file contents and the complete new payload, with all scripts guarded inside isolated roots. Existing r93 bridge and stable feeds are unchanged.
