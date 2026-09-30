# Tests

Run the receiver-independent safety checks with:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

These tests cover thermal reading normalization/deduplication, `/proc/<pid>/cmdline` NUL parsing, OSCam argument secrecy, release asset validation, IPK version mismatch rejection, and avoiding slow repository queries in the GUI. They do not replace a real Enigma2 receiver test.
