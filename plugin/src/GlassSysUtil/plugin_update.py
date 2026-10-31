"""Warder plugin release checks and verified IPK installation (Python 3)."""

import hashlib
import io
import json
import pathlib
import re
import ssl
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from urllib.request import Request, urlopen

REPOSITORY = "Evolution-by-Warder/GSU-Warder-Evolution"
PACKAGE_ID = "enigma2-plugin-extensions-gsu-warder-evolution"
LEGACY_PACKAGE_ID = "enigma2-plugin-glasssysutil"
DOWNLOAD_PREFIX = "enigma2-plugin-extensions-gsu"
MIGRATION_FLAG = pathlib.Path("/var/lib/warder-gsu/package-rename-in-progress")
# The recovered runtime has its own feed; production dashboards never enter it.
FEED_URL = "https://raw.githubusercontent.com/" + REPOSITORY + "/original-python314/plugin/update/stable.json"
MAX_IPK_BYTES = 128 * 1024 * 1024


class UpdateError(ValueError):
    pass


def version_key(value):
    if not isinstance(value, str):
        raise UpdateError("Invalid plugin version")
    match = re.fullmatch(r"(\d+)\.(\d+)-r(\d+)", value)
    if not match:
        raise UpdateError("Invalid restoration version")
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str
    bytes: int
    notes: str = ""
    notes_i18n: dict = field(default_factory=dict)
    package_id: str = PACKAGE_ID


def parse_release(payload, current_version):
    """Return a newer published release, never a work commit or downgrade."""
    current = version_key(current_version)
    try:
        document = json.loads(payload)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise UpdateError("Invalid release manifest") from exc
    if not isinstance(document, dict) or type(document.get("schema")) is not int or document["schema"] != 1:
        raise UpdateError("Unsupported release manifest")
    if document.get("product") != "Glass System Utility Warder Evolution" or document.get("channel") != "original-python314":
        raise UpdateError("Wrong update product or channel")
    if "release" not in document:
        raise UpdateError("Missing release entry")
    item = document["release"]
    if item is None:
        return None
    if not isinstance(item, dict):
        raise UpdateError("Invalid release entry")
    remote = version_key(item.get("version"))
    tag = item.get("tag")
    if tag not in (item["version"], "v" + item["version"]):
        raise UpdateError("Release tag does not match version")
    root = "https://github.com/" + REPOSITORY + "/releases/download/" + tag + "/"
    suffix = "_" + item["version"] + "_all.ipk"
    allowed = {root + prefix + suffix: identity for prefix, identity in (
        (PACKAGE_ID, PACKAGE_ID), (DOWNLOAD_PREFIX, PACKAGE_ID), (LEGACY_PACKAGE_ID, LEGACY_PACKAGE_ID))}
    expected = item.get("url")
    if expected not in allowed:
        raise UpdateError("Unexpected plugin package URL")
    digest, size, notes = item.get("sha256"), item.get("bytes"), item.get("notes", "")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise UpdateError("Missing package SHA256")
    if type(size) is not int or not 0 < size <= MAX_IPK_BYTES:
        raise UpdateError("Invalid package size")
    if not isinstance(notes, str) or len(notes) > 8192:
        raise UpdateError("Invalid release notes")
    translated_notes = item.get("notes_i18n", {})
    if (not isinstance(translated_notes, dict) or len(translated_notes) > 32 or
            any(not isinstance(k, str) or not re.fullmatch(r"[a-z]{2,3}", k) or
                not isinstance(v, str) or len(v) > 8192 for k,v in translated_notes.items())):
        raise UpdateError("Invalid translated release notes")
    if remote <= current:
        return None
    return Release(item["version"], expected, digest, size, notes, translated_notes, allowed[expected])


def _open(url, timeout=6):
    request = Request(url, headers={"User-Agent": "GSU-Warder-Evolution", "Cache-Control": "no-cache"})
    # Explicit context remains verified even when another legacy plugin changes
    # urllib's process-wide default SSL context.
    return urlopen(request, timeout=timeout, context=ssl.create_default_context())


def check_release(current_version, opener=_open):
    with opener(FEED_URL) as response:
        payload = response.read(65537)
    if len(payload) > 65536:
        raise UpdateError("Release manifest is too large")
    return parse_release(payload, current_version)


def download_release(release, destination, opener=_open):
    """Write only to the private staging area; validate before invoking opkg."""
    path = pathlib.Path(destination)
    digest, count, created = hashlib.sha256(), 0, False
    try:
        with path.open("xb") as target:
            created = True
            with opener(release.url, timeout=15) as response:
                while True:
                    data = response.read(128 * 1024)
                    if not data:
                        break
                    count += len(data)
                    if count > release.bytes:
                        raise UpdateError("Package exceeds published size")
                    digest.update(data)
                    target.write(data)
        if count != release.bytes or digest.hexdigest() != release.sha256:
            raise UpdateError("Package size or SHA256 mismatch")
        return path
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


def _control_archive(path):
    """Read the control member of either common IPK container, without extraction."""
    with path.open("rb") as source:
        if source.read(8) == b"!<arch>\n":
            while True:
                header = source.read(60)
                if not header:
                    break
                if len(header) != 60 or header[58:] != b"`\n":
                    raise UpdateError("Invalid IPK header")
                try:
                    size = int(header[48:58])
                    name = header[:16].decode("ascii").strip().rstrip("/")
                except (ValueError, UnicodeError) as exc:
                    raise UpdateError("Invalid IPK member") from exc
                if size < 0 or source.tell() + size > path.stat().st_size:
                    raise UpdateError("Truncated IPK member")
                if name in ("control.tar.gz", "control.tar.xz", "control.tar.bz2", "control.tar"):
                    if size > 4 * 1024 * 1024:
                        raise UpdateError("IPK control archive is too large")
                    return source.read(size)
                source.seek(size + (size % 2), 1)
    try:
        with tarfile.open(path, "r:*") as outer:
            for item in outer:
                if item.name.removeprefix("./") in ("control.tar.gz", "control.tar.xz", "control.tar.bz2", "control.tar"):
                    if not item.isfile() or item.size > 4 * 1024 * 1024:
                        raise UpdateError("Invalid IPK control archive")
                    return outer.extractfile(item).read()
    except tarfile.TarError as exc:
        raise UpdateError("Invalid IPK archive") from exc
    raise UpdateError("IPK control archive is missing")


def validate_ipk(path, release):
    try:
        with tarfile.open(fileobj=io.BytesIO(_control_archive(path)), mode="r:*") as control:
            members = [m for m in control if m.name.removeprefix("./") == "control"]
            if len(members) != 1 or not members[0].isfile() or members[0].size > 65536:
                raise UpdateError("Invalid IPK control metadata")
            text = control.extractfile(members[0]).read(65537).decode("utf-8")
    except (tarfile.TarError, UnicodeError) as exc:
        raise UpdateError("Invalid IPK control metadata") from exc
    fields = {}
    for line in text.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            if key in fields:
                raise UpdateError("Duplicate IPK control field")
            fields[key] = value.strip()
    if fields.get("Package") != release.package_id or fields.get("Version") != release.version or fields.get("Architecture") != "all":
        raise UpdateError("IPK package identity, version or architecture mismatch")


def verify_installation(expected_version, package_id=PACKAGE_ID, runner=subprocess.run):
    # Use the newly installed helper, even while the old GUI remains in memory.
    helper = pathlib.Path(__file__).parent / 'install_health.py'
    result = runner(['/usr/bin/python3', str(helper), '--expected-version',
                     expected_version, '--package', package_id], stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, timeout=30)
    if result.returncode != 0:
        raise UpdateError('GSU installation verification failed: ' + result.stdout[-2000:])


def install_release(release, opener=_open, runner=subprocess.run, verifier=None):
    """Stage and validate both packages before a guarded identity replacement."""
    with tempfile.TemporaryDirectory(prefix="gsu-plugin-update-") as temporary:
        work = pathlib.Path(temporary)
        path = download_release(release, work / "update.ipk", opener)
        validate_ipk(path, release)
        migrating = False
        rollback_path = None
        if release.package_id == PACKAGE_ID and version_key(release.version) >= version_key("13.40-r94"):
            status = runner(["opkg", "status", LEGACY_PACKAGE_ID], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=30)
            fields = dict(line.split(": ", 1) for line in status.stdout.splitlines() if ": " in line)
            if fields.get("Package") == LEGACY_PACKAGE_ID and fields.get("Status", "").split()[-1:] == ["installed"]:
                if fields.get("Version") != "13.40-r93":
                    raise UpdateError("Install the compatible r93 transition update first")
                legacy_feed = "https://raw.githubusercontent.com/" + REPOSITORY + "/original-python314/plugin/update/candidate.json"
                with opener(legacy_feed) as response:
                    payload = response.read(65537)
                if len(payload) > 65536:
                    raise UpdateError("Legacy recovery manifest is too large")
                previous = parse_release(payload, "0.0-r0")
                if previous is None or previous.package_id != LEGACY_PACKAGE_ID or previous.version != fields["Version"]:
                    raise UpdateError("Compatible recovery package is unavailable; installed GSU was retained")
                rollback_path = download_release(previous, work / "rollback.ipk", opener)
                validate_ipk(rollback_path, previous)
                MIGRATION_FLAG.parent.mkdir(parents=True, exist_ok=True)
                with MIGRATION_FLAG.open("x") as flag:
                    flag.write(release.version + "\n")
                migrating = True
        try:
            if migrating:
                removed = runner(["opkg", "remove", LEGACY_PACKAGE_ID], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, timeout=300)
                if removed.returncode != 0:
                    raise UpdateError("Legacy package could not be removed: " + removed.stdout[-2000:])
            try:
                result = runner(["opkg", "install", str(path)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=300)
                if result.returncode != 0:
                    raise UpdateError("opkg failed (%s): %s" % (result.returncode, result.stdout[-2000:]))
                (verifier or verify_installation)(release.version, package_id=release.package_id, runner=runner)
            except Exception as failure:
                if rollback_path is not None:
                    try:
                        cleared = runner(["opkg", "remove", PACKAGE_ID], stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, timeout=300)
                        if cleared.returncode != 0:
                            raise UpdateError("Incomplete replacement could not be removed")
                        restored = runner(["opkg", "install", str(rollback_path)], stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True, timeout=300)
                        if restored.returncode != 0:
                            raise UpdateError("Recovery installation failed")
                    except Exception as recovery:
                        saved = MIGRATION_FLAG.parent / "recovery-r93.ipk"
                        saved.write_bytes(rollback_path.read_bytes())
                        raise UpdateError("Update and recovery failed; verified recovery IPK retained at " + str(saved)) from recovery
                    raise UpdateError("Update failed; previous GSU was restored") from failure
                raise
        finally:
            if migrating:
                MIGRATION_FLAG.unlink(missing_ok=True)
    return release.version
