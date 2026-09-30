# Test policy

Real receiver testing is authoritative for Enigma2 integration.

The initial modern source-core baseline, 13.21-w2, has been installed and functionally tested on a GigaBlue Quad 4K Pro running Python 3.14.

For every migrated area:

- syntax/host checks first where possible
- installation/upgrade behavior checked separately
- read-only functionality before write functionality
- destructive or persistent actions require explicit test cases
- no autostart activation until the called components are individually stable

A successful import is not treated as proof that an Enigma2 feature is safe.
