#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/dist"
PKG="$ROOT/build/ipk-root"
rm -rf "$PKG"
mkdir -p "$PKG/CONTROL" "$PKG/usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil" "$OUT"
cp "$ROOT/packaging/CONTROL/control" "$PKG/CONTROL/control"
cp "$ROOT/packaging/CONTROL/postinst" "$PKG/CONTROL/postinst"
chmod 755 "$PKG/CONTROL/postinst"
cp "$ROOT/src/GlassSysUtil/"* "$PKG/usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil/"
chmod 644 "$PKG/usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil/"*
opkg-build "$PKG" "$OUT"
