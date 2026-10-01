#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
VERSION="$(tr -d '\r\n' < "$ROOT/src/GlassSysUtil/version")"
PACKAGE="enigma2-plugin-glasssysutil_${VERSION}_all.ipk"
OUT="$ROOT/dist"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM

test -n "$VERSION"
grep -Fqx "Version: $VERSION" "$ROOT/packaging/CONTROL/control"
python3 -m py_compile "$ROOT/src/GlassSysUtil/plugin.py"
test -s "$ROOT/src/GlassSysUtil/SysMgt.png"

ROOTFS="$WORK/root"
CONTROL="$WORK/control"
PLUGIN="$ROOTFS/usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil"
mkdir -p "$PLUGIN" "$CONTROL" "$OUT"
cp "$ROOT/src/GlassSysUtil/plugin.py" "$ROOT/src/GlassSysUtil/__init__.py" \
   "$ROOT/src/GlassSysUtil/version" "$ROOT/src/GlassSysUtil/SysMgt.png" "$PLUGIN/"
if [ -d "$ROOT/src/GlassSysUtil/locale" ]; then
    cp -R "$ROOT/src/GlassSysUtil/locale" "$PLUGIN/"
    for po in "$PLUGIN"/locale/*/LC_MESSAGES/GlassSysUtil.po; do
        msgfmt --check "$po" -o "${po%.po}.mo"
    done
    find "$PLUGIN/locale" -type f -name '*.po' -delete
    for lang in sk cs de pl it es fr; do
        test -s "$PLUGIN/locale/$lang/LC_MESSAGES/GlassSysUtil.mo"
    done
fi
cp "$ROOT/packaging/CONTROL/control" "$ROOT/packaging/CONTROL/postinst" "$CONTROL/"
chmod 755 "$CONTROL/postinst"
printf '2.0\n' > "$WORK/debian-binary"

tar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner \
    -cf - -C "$CONTROL" . | gzip -n > "$WORK/control.tar.gz"
tar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner \
    -cf - -C "$ROOTFS" usr | gzip -n > "$WORK/data.tar.gz"
(cd "$WORK" && ar rcD "$OUT/$PACKAGE" debian-binary control.tar.gz data.tar.gz)

MEMBERS="$(ar t "$OUT/$PACKAGE" | tr '\n' ' ')"
test "$MEMBERS" = "debian-binary control.tar.gz data.tar.gz "
ar p "$OUT/$PACKAGE" control.tar.gz | tar -xzOf - ./control | grep -Fqx "Package: enigma2-plugin-glasssysutil"
ar p "$OUT/$PACKAGE" control.tar.gz | tar -xzOf - ./control | grep -Fqx "Version: $VERSION"
ar p "$OUT/$PACKAGE" data.tar.gz | tar -tzf - | grep -Fq 'usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil/plugin.py'
sha256sum "$OUT/$PACKAGE" | tee "$OUT/$PACKAGE.sha256"
printf 'Built %s\n' "$OUT/$PACKAGE"
