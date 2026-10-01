# -*- coding: utf-8 -*-
"""
Glass System Utility - Warder Evolution
Modern source core. Original Glass System Utility authorship is respected.
"""

from __future__ import absolute_import

import os
import platform
import shutil
import socket
import subprocess
import json
import re
import tarfile
import time
import tempfile
import threading
import urllib.request
import urllib.error
from urllib.parse import urlsplit

from Plugins.Plugin import PluginDescriptor
try:
    from . import _
except (ImportError, ValueError):
    # Standalone import is used by the regression harness; Enigma2 loads the
    # package normally and therefore uses the gettext implementation above.
    _ = lambda text: text
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
try:
    from Components.ScrollLabel import ScrollLabel
except ImportError:
    ScrollLabel = None
from Components.MenuList import MenuList
try:
    from Components.ProgressBar import ProgressBar
except ImportError:
    ProgressBar = Label
try:
    from Components.Sources.List import List
    from Components.MultiContent import MultiContentEntryText
    from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER
except ImportError:
    List = None
    MultiContentEntryText = None
    eListboxPythonMultiContent = None
    gFont = None
    RT_HALIGN_LEFT = 0
    RT_VALIGN_CENTER = 0
try:
    from enigma import eTimer
except ImportError:
    eTimer = None

def _installed_version():
    try:
        with open(os.path.join(os.path.dirname(__file__), "version"), "r") as handle:
            value = handle.read().strip()
        return value or "unknown"
    except Exception:
        return "unknown"


VERSION = _installed_version()
UPDATE_API = "https://api.github.com/repos/Evolution-by-Warder/Glass-System-Utility-Warder-Evolution/releases/latest"


def _read_text(path, default="N/A"):
    try:
        with open(path, "r") as handle:
            value = handle.read().strip()
        return value or default
    except Exception:
        return default


def _read_lines(path):
    try:
        with open(path, "r") as handle:
            return handle.readlines()
    except Exception:
        return []


def _run(argv, timeout=3):
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=timeout, check=False)
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def _run_status(argv, timeout=3):
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=timeout, check=False)
        return proc.returncode, (proc.stdout or "").strip()
    except Exception:
        return -1, ""


def _uptime():
    try:
        seconds = int(float(_read_text("/proc/uptime", "0").split()[0]))
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, _ = divmod(seconds, 60)
        return "%dd %02d:%02d" % (days, hours, minutes)
    except Exception:
        return "N/A"


def _default_gateway():
    for line in _read_lines("/proc/net/route")[1:]:
        fields = line.split()
        if len(fields) >= 4 and fields[1] == "00000000":
            try:
                raw = bytes.fromhex(fields[2])
                return socket.inet_ntoa(raw[::-1])
            except Exception:
                pass
    return "N/A"


def _ipv4_for_interface(name):
    ip = _run(["ip", "-4", "-o", "addr", "show", "dev", name])
    for line in ip.splitlines():
        fields = line.split()
        if "inet" in fields:
            try:
                return fields[fields.index("inet") + 1]
            except Exception:
                pass
    return "N/A"


def hardware_identity_information():
    """Read receiver identity and exposed hardware capabilities without vendor branching."""
    brand_paths = ("/proc/stb/info/brand",)
    model_paths = ("/proc/stb/info/model", "/proc/stb/info/boxtype", "/proc/device-tree/model")
    serial_paths = ("/proc/stb/info/serial", "/proc/stb/info/serial_number")
    def first(paths, default="N/A"):
        for path in paths:
            value = _read_text(path, "")
            if value:
                return value.replace("\x00", "").strip()
        return default

    rows = [
        "Brand: %s" % first(brand_paths),
        "Model: %s" % first(model_paths),
        "Architecture: %s" % platform.machine(),
        "Kernel: %s" % platform.release(),
    ]
    cpu = ""
    for line in _read_lines("/proc/cpuinfo"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() in ("model name", "hardware", "cpu model", "processor"):
            cpu = value.strip()
            if cpu:
                break
    rows.append(_("CPU: %s") % (cpu or _("N/A")))
    # Serial is deliberately reported only as presence, not exposed in UI.
    serial_present = any(bool(_read_text(path, "")) for path in serial_paths)
    rows.append(_("Hardware serial interface: %s") % (_("available (hidden)") if serial_present else _("not exposed")))

    cpu_count = os.cpu_count()
    rows.append(_("CPU cores: %s") % (cpu_count if cpu_count is not None else _("N/A")))

    freq_values = []
    cpu_root = "/sys/devices/system/cpu"
    try:
        for name in sorted(os.listdir(cpu_root)):
            if not name.startswith("cpu") or not name[3:].isdigit():
                continue
            raw = _read_text(os.path.join(cpu_root, name, "cpufreq/scaling_cur_freq"), "")
            if raw.isdigit():
                freq_values.append(int(raw) / 1000.0)
    except Exception:
        pass
    if freq_values:
        rows.append(_("CPU frequency: %.0f-%.0f MHz") % (min(freq_values), max(freq_values)))

    return "\n".join(rows)


def system_information():
    model = _read_text("/proc/stb/info/model", platform.machine())
    brand = _read_text("/proc/stb/info/brand", "")
    chipset = _read_text("/proc/stb/info/chipset", "")
    boxtype = _read_text("/proc/stb/info/boxtype", "")
    image = _read_text("/etc/image-version", "N/A")
    cpu = "N/A"
    for line in _read_lines("/proc/cpuinfo"):
        if ":" in line and line.lower().startswith(("model name", "processor")):
            cpu = line.split(":", 1)[1].strip()
            if cpu:
                break
    rows = (
        "Glass System Utility - Warder Evolution %s" % VERSION, "",
        "Receiver: %s %s" % (brand, model),
        "Box type: %s" % (boxtype or "N/A"),
        "Chipset: %s" % (chipset or "N/A"),
        "Hostname: %s" % socket.gethostname(),
        "CPU: %s" % cpu,
        "Architecture: %s" % platform.machine(),
        "Kernel: %s" % platform.release(),
        "Python: %s" % platform.python_version(),
        "Uptime: %s" % _uptime(),
        "Image: %s" % image,
    )
    return "\n".join(rows)

def network_information():
    rows = [_("Default gateway: %s") % _default_gateway()]
    resolvers = []
    for line in _read_lines("/etc/resolv.conf"):
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "nameserver":
            resolvers.append(fields[1])
    rows.append(_("DNS: %s") % (", ".join(resolvers) if resolvers else _("N/A")))
    rows.append("")
    try:
        names = sorted(os.listdir("/sys/class/net"))
    except Exception:
        names = []
    for name in names:
        state = _read_text("/sys/class/net/%s/operstate" % name, "unknown")
        mac = _read_text("/sys/class/net/%s/address" % name, "N/A")
        rows.append("%s  [%s]" % (name, state))
        rows.append("  IPv4: %s" % _ipv4_for_interface(name))
        rows.append("  MAC:  %s" % mac)
    return "\n".join(rows)


def storage_information():
    rows, seen = [], set()
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) < 3:
            continue
        device, mountpoint, fstype = fields[:3]
        if mountpoint in seen or not device.startswith("/dev/"):
            continue
        seen.add(mountpoint)
        try:
            usage = shutil.disk_usage(mountpoint)
            used = usage.total - usage.free
            pct = (used * 100.0 / usage.total) if usage.total else 0
            rows.append("%s -> %s [%s]\n  %.1f / %.1f GiB  (%.0f%%)" % (
                device, mountpoint, fstype, used / 1073741824.0,
                usage.total / 1073741824.0, pct))
        except Exception:
            rows.append("%s -> %s [%s]" % (device, mountpoint, fstype))
    return "\n\n".join(rows) if rows else "No physical storage mounts found."


def memory_information():
    wanted = ("MemTotal", "MemAvailable", "MemFree", "Buffers", "Cached", "SwapTotal", "SwapFree")
    values = {}
    for line in _read_lines("/proc/meminfo"):
        if ":" in line:
            key, value = line.split(":", 1)
            if key in wanted:
                values[key] = value.strip()
    return "\n".join("%s: %s" % (key, values.get(key, "N/A")) for key in wanted)



def device_manager_information():
    """Read-only device manager inventory including mounted and block devices."""
    rows = [_("Detected mounted devices")]
    mounted = set()
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) < 4 or not fields[0].startswith("/dev/"):
            continue
        device, mountpoint, fstype, options = fields[:4]
        mounted.add(os.path.basename(device))
        mode = _("read-only") if "ro" in options.split(",") else _("read/write")
        try:
            usage = shutil.disk_usage(mountpoint)
            rows.append("%s -> %s [%s, %s]" % (device, mountpoint, fstype, mode))
            rows.append("  %.1f / %.1f GiB  (%s free)" % ((usage.total - usage.free) / 1073741824.0, usage.total / 1073741824.0, _human_bytes(usage.free)))
        except Exception:
            rows.append("%s -> %s [%s, %s]" % (device, mountpoint, fstype, mode))
    rows += ["", _("Block devices")]
    try:
        names = sorted(name for name in os.listdir("/sys/class/block") if not name.startswith(("loop", "ram", "zram")))
    except Exception:
        names = []
    if not names:
        rows.append(_("not exposed"))
    for name in names[:24]:
        sectors = _read_text("/sys/class/block/%s/size" % name, "0")
        try:
            size = _human_bytes(int(sectors) * 512)
        except Exception:
            size = _("N/A")
        base = "/sys/class/block/%s" % name
        model = _read_text(os.path.join(base, "device/model"), "").strip()
        vendor = _read_text(os.path.join(base, "device/vendor"), "").strip()
        removable = _read_text(os.path.join(base, "removable"), "").strip()
        kind = _("removable") if removable == "1" else _("fixed")
        description = " ".join(value for value in (vendor, model) if value).strip()
        rows.append("%s  %s  %s  %s" % (
            name, size, kind, _("mounted") if name in mounted else _("not mounted directly")))
        if description:
            rows.append("  %s" % description)
    rows += ["", _("Safety: format, partition, mount and unmount actions are disabled until receiver validation.")]
    return "\n".join(rows)

def swap_manager_information():
    """Read-only original-style swap inventory with capacity and priority."""
    rows = [_("Swap status")]
    lines = _read_lines("/proc/swaps")
    total_kib = used_kib = 0
    if len(lines) <= 1:
        rows.append(_("No active swap devices/files."))
    else:
        for line in lines[1:]:
            fields = line.split()
            if len(fields) >= 5:
                try:
                    size, used = int(fields[2]), int(fields[3])
                    total_kib += size
                    used_kib += used
                except Exception:
                    pass
                rows.append("%s" % fields[0])
                rows.append("  %s | %s KiB / %s KiB | priority %s" % (fields[1], fields[3], fields[2], fields[4]))
    rows += ["", _("Active swap total: %.1f MiB") % (total_kib / 1024.0),
             _("Active swap used: %.1f MiB") % (used_kib / 1024.0), "", memory_information(), "",
             _("Safety: swap enable/disable/create actions remain gated until real-receiver validation.")]
    return "\n".join(rows)

def package_tools_information():
    """Read-only capability and local-content audit for the original package/script center."""
    package_manager = "opkg" if shutil.which("opkg") else ("apt" if shutil.which("apt") else "")
    shell = shutil.which("sh") or ""
    rows = [
        _("Package manager: %s") % (package_manager or _("not detected")),
        _("Shell capability: %s") % (shell or _("not detected")),
        _("IPK support: %s") % (_("available") if package_manager == "opkg" else _("not detected")),
        _("DEB support: %s") % (_("available") if package_manager == "apt" else _("not detected")),
    ]
    roots = ("/tmp", "/media/hdd", "/media/usb", "/usr/script")
    total = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            names = sorted(os.listdir(root))
        except Exception:
            continue
        candidates = [name for name in names if name.lower().endswith((".ipk", ".deb", ".tar", ".tar.gz", ".tgz", ".sh"))]
        total += len(candidates)
        if candidates:
            rows += ["", _("%s local candidates: %d") % (root, len(candidates))]
            for name in candidates[:5]:
                path = os.path.join(root, name)
                try:
                    rows.append("  %s  (%s)" % (name, _human_bytes(os.path.getsize(path))))
                except Exception:
                    rows.append("  %s" % name)
    rows += ["", _("Detected local package/script candidates: %d") % total,
             _("User scripts require explicit local execution; legacy remote installers are not restored."),
             _("Package/script state changes remain gated until receiver validation.")]
    return "\n".join(rows)

def package_center_selection_information(index):
    """Read-only detail for one original package/script-center operation."""
    labels = (_("User scripts"), _("Install IPK"), _("Uninstall IPK"), _("Install TAR"), _("Install/Uninstall DEB"))
    title = labels[index] if 0 <= index < len(labels) else _("Package tools")
    rows = [title, "=" * 42, ""]
    if index == 0:
        roots, suffixes = ("/usr/script", "/tmp", "/media/hdd", "/media/usb"), (".sh",)
    elif index == 1:
        roots, suffixes = ("/tmp", "/media/hdd", "/media/usb"), (".ipk",)
    elif index == 2:
        manager = "opkg" if shutil.which("opkg") else ""
        rows += [_("Package manager: %s") % (manager or _("not detected")),
                 _("Installed-package removal remains gated until receiver validation.")]
        return "\n".join(rows)
    elif index == 3:
        roots, suffixes = ("/tmp", "/media/hdd", "/media/usb"), (".tar", ".tar.gz", ".tgz")
    else:
        manager = "apt" if shutil.which("apt") else ""
        rows.append(_("DEB package manager: %s") % (manager or _("not detected")))
        roots, suffixes = ("/tmp", "/media/hdd", "/media/usb"), (".deb",)
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            names = sorted(name for name in os.listdir(root) if name.lower().endswith(suffixes))
        except Exception:
            continue
        for name in names[:12]:
            path = os.path.join(root, name)
            try:
                found.append("%s  (%s)" % (path, _human_bytes(os.path.getsize(path))))
            except Exception:
                found.append(path)
    rows += found if found else [_("No matching local candidates detected.")]
    rows += ["", _("State-changing actions remain gated until receiver validation.")]
    return "\n".join(rows)


def automatic_installation_information():
    """Read-only local inventory for the original automatic-installation center."""
    roots = ("/etc/enigma2", "/usr/script", "/media/hdd", "/media/usb")
    rows = [_("Automatic installation"), ""]
    total = 0
    types = {".ipk": 0, ".deb": 0, ".sh": 0, "archive": 0}
    for path in roots:
        if not os.path.exists(path):
            rows.append("%s: %s" % (path, _("not detected")))
            continue
        try:
            entries = sorted(os.listdir(path))
            candidates = [name for name in entries if name.lower().endswith((".ipk", ".deb", ".tar", ".tar.gz", ".tgz", ".sh"))]
            total += len(candidates)
            rows.append("%s: %d %s" % (path, len(candidates), _("local install candidates")))
            for name in candidates[:6]:
                low = name.lower()
                if low.endswith(".ipk"): types[".ipk"] += 1
                elif low.endswith(".deb"): types[".deb"] += 1
                elif low.endswith(".sh"): types[".sh"] += 1
                else: types["archive"] += 1
                candidate = os.path.join(path, name)
                try:
                    rows.append("  %s  (%s)" % (name, _human_bytes(os.path.getsize(candidate))))
                except Exception:
                    rows.append("  %s" % name)
            if len(candidates) > 6:
                rows.append(_("  ... and %d more") % (len(candidates) - 6))
        except Exception:
            rows.append("%s: %s" % (path, _("detected")))
    rows += ["", _("Total local candidates: %d") % total,
             _("IPK: %d | DEB: %d | scripts: %d | archives: %d") % (types[".ipk"], types[".deb"], types[".sh"], types["archive"]),
             _("Legacy remote installers are not executed."),
             _("Local install actions remain gated until receiver validation.")]
    return "\n".join(rows)

def osd_ecm_information():
    """Original OSD ECM compatibility view backed by live modern CAM/service data."""
    active = _active_cam()
    service = current_service_technical_information()
    caids = service.get("caids") or []
    rows = [
        _("Current service: %s") % (service.get("name") or _("not exposed")),
        _("Provider: %s") % (service.get("provider") or _("not exposed")),
        active_cam_summary() if active else _("No supported active CAM detected."),
        _("Available CAIDs: %s") % (", ".join("%04X" % value for value in caids) if caids else _("not exposed")),
    ]
    if active and active.get("family") == "oscam":
        live, reason = oscam_live_rows()
        if live:
            values = _oscam_table_values(live[0])
            rows += ["", _("Reader / User: %s") % (values["name"] or "N/A"),
                     _("Protocol: %s") % (values["protocol"] or "N/A"),
                     _("Channel: %s") % (values["channel"] or service.get("name") or "N/A"),
                     _("ECM: %s") % (values["ecm"] or "N/A"),
                     _("Status: %s") % (values["status"] or "N/A")]
        elif reason:
            rows += ["", reason]
    rows += ["", _("OSD ECM display settings remain gated until receiver validation.")]
    return "\n".join(rows)

def legacy_cam_information(family):
    """Read-only original-style runtime view for legacy CAM families."""
    definitions = {
        "cccam": ("CCcam", "cccam", ("/etc/CCcam.cfg", "/etc/CCcam/CCcam.cfg", "/usr/keys/CCcam.cfg", "/var/keys/CCcam.cfg")),
        "mbox": ("Mbox", "mbox", ("/var/keys/mbox.cfg", "/usr/keys/mbox.cfg", "/etc/mbox.cfg", "/etc/tuxbox/config/mbox.cfg")),
    }
    label, needle, configs = definitions.get(family, (family, family, ()))
    matches = _find_processes(needle)
    rows = [_("%s runtime") % label, _("Process: %s") % (_("RUNNING") if matches else _("not detected"))]
    if matches:
        rows.append(_("Process IDs: %s") % ", ".join(pid for pid, argv in matches[:8]))
        for pid, argv in matches[:3]:
            if argv:
                rows.append(_("Executable: %s") % os.path.basename(argv[0]))
    found = [path for path in configs if os.path.isfile(path)]
    rows += ["", _("Configuration: %s") % (found[0] if found else _("not detected"))]
    if found:
        try:
            rows.append(_("Configuration size: %s") % _human_bytes(os.path.getsize(found[0])))
        except Exception:
            pass
    rows += ["", _("Configuration contents and credentials are never displayed."),
             _("Legacy CAM state changes remain disabled until receiver validation.")]
    return "\n".join(rows)


def conditional_legacy_cam_information():
    """Compact legacy CAM capability overview used by diagnostics."""
    families = (("CCcam", "cccam"), ("Mbox", "mbox"), ("MGcamd", "mgcamd"), ("NCam", "ncam"))
    return "\n".join("%s: %s" % (label, _("RUNNING") if _find_processes(needle) else _("not detected"))
                     for label, needle in families)


def cron_manager_information():
    """Read-only cron capability and bounded schedule preview for the original manager."""
    rows = []
    cron_proc = bool(_find_processes("crond") or _find_processes("cron"))
    rows.append(_("Crond process: %s") % (_("RUNNING") if cron_proc else _("not detected")))
    locations = ("/etc/cron.d", "/etc/crontabs", "/var/spool/cron", "/var/spool/cron/crontabs")
    found, samples, previews = [], [], []
    jobs = 0
    for path in locations:
        targets = []
        if os.path.isdir(path):
            found.append(path)
            try:
                targets = [os.path.join(path, name) for name in sorted(os.listdir(path)) if not name.startswith(".")]
            except Exception:
                targets = []
        elif os.path.isfile(path):
            found.append(path)
            targets = [path]
        jobs += len(targets)
        samples.extend(targets[:5])
        for target in targets[:4]:
            for line in _read_lines(target):
                line = line.strip()
                if line and not line.startswith("#"):
                    fields = line.split()
                    if len(fields) >= 6:
                        previews.append("%s: %s %s %s %s %s  %s" % (
                            os.path.basename(target), fields[0], fields[1], fields[2], fields[3], fields[4],
                            " ".join(fields[5:])[:90]))
                        break
            if len(previews) >= 8:
                break
    rows.append(_("Cron storage: %s") % (", ".join(found) if found else _("not detected")))
    rows.append(_("Cron entries/files: %d") % jobs)
    if samples:
        rows += ["", _("Detected cron files")] + samples[:12]
    if previews:
        rows += ["", _("Schedule preview")] + previews[:8]
    rows += ["", _("Editing/enabling scheduled jobs remains disabled until receiver validation.")]
    return "\n".join(rows)

def text_editor_information():
    """Safe read-only inventory for the original text-editor workflow."""
    roots = ("/etc/enigma2", "/etc/tuxbox/config", "/usr/keys", "/var/keys")
    preferred = ("/etc/enigma2/settings", "/etc/hosts", "/etc/resolv.conf", "/etc/fstab", "/etc/hostname")
    rows = [_("Text editor capability"), _("Readable common configuration files")]
    seen = set()
    for path in preferred:
        if os.path.isfile(path):
            seen.add(path)
            try:
                rows.append("%s  (%s)" % (path, _human_bytes(os.path.getsize(path))))
            except Exception:
                rows.append(path)
    rows += ["", _("Detected text/config files")]
    detected = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            names = sorted(os.listdir(root))
        except Exception:
            continue
        for name in names:
            path = os.path.join(root, name)
            if path in seen or not os.path.isfile(path):
                continue
            if name.lower().endswith((".conf", ".cfg", ".txt", ".xml", ".list", ".json")):
                try:
                    detected.append("%s  (%s)" % (path, _human_bytes(os.path.getsize(path))))
                except Exception:
                    detected.append(path)
            if len(detected) >= 16:
                break
        if len(detected) >= 16:
            break
    rows += detected if detected else [_("No additional text/config candidates detected.")]
    rows += ["", _("Arbitrary system-file editing is intentionally not enabled in this migration stage.")]
    return "\n".join(rows)

def root_password_information():
    """Security-reviewed status for the legacy root password reset function."""
    passwd = _read_text("/etc/passwd", "")
    root_line = next((line for line in passwd.splitlines() if line.startswith("root:")), "")
    rows = [_("Root account: %s") % (_("detected") if root_line else _("not detected"))]
    if root_line:
        fields = root_line.split(":")
        if len(fields) >= 7:
            rows += [_("UID: %s") % fields[2], _("GID: %s") % fields[3], _("Home: %s") % fields[5], _("Shell: %s") % fields[6]]
    shadow_present = os.path.isfile("/etc/shadow")
    rows.append(_("Shadow password database: %s") % (_("detected") if shadow_present else _("not detected")))
    rows.append(_("Interactive password tool: %s") % (_("available") if shutil.which("passwd") else _("not detected")))
    rows.append(_("Root shell usable: %s") % (_("yes") if root_line and len(root_line.split(":")) >= 7 and root_line.split(":")[6] not in ("/bin/false", "/sbin/nologin") else _("no")))
    rows += ["", _("Password reset is not exposed without a dedicated confirmation and receiver-safe implementation.")]
    return "\n".join(rows)

def channel_settings_information():
    """Read-only inventory of Enigma2 channel-setting files; never modifies bouquets."""
    root = "/etc/enigma2"
    rows = [_("Enigma2 channel settings")]
    if not os.path.isdir(root):
        rows.append(_("not detected"))
        return "\n".join(rows)
    try:
        names = sorted(os.listdir(root))
    except Exception:
        names = []
    bouquets = [name for name in names if name.startswith(("bouquets.", "userbouquet."))]
    lamedb = [name for name in names if name.startswith("lamedb")]
    satellites = [name for name in names if name in ("satellites.xml", "terrestrial.xml", "cables.xml")]
    rows += [_("Settings root: %s") % root, _("Bouquet files: %d") % len(bouquets),
             _("Service database files: %d") % len(lamedb), _("Tuning definition files: %d") % len(satellites)]
    if satellites:
        rows += ["", _("Tuning definitions")] + ["  " + name for name in satellites]
    if lamedb:
        rows += ["", _("Service databases")]
        for name in lamedb[:6]:
            path = os.path.join(root, name)
            try: rows.append("  %s  (%s)" % (name, _human_bytes(os.path.getsize(path))))
            except Exception: rows.append("  %s" % name)
    if bouquets:
        rows += ["", _("Detected bouquets")]
        for name in bouquets[:12]:
            path = os.path.join(root, name)
            try:
                size = _human_bytes(os.path.getsize(path))
                refs = sum(1 for line in _read_lines(path) if line.startswith("#SERVICE"))
                rows.append("  %s  (%s, %d services)" % (name, size, refs))
            except Exception:
                rows.append("  %s" % name)
        if len(bouquets) > 12: rows.append(_("... and %d more") % (len(bouquets) - 12))
    rows += ["", _("Bouquet/channel modification remains disabled until receiver validation.")]
    return "\n".join(rows)

def service_information():
    rows = []
    patterns = ("enigma2", "oscam", "cccam", "ncam", "mgcamd", "samba", "smbd",
                "nmbd", "dropbear", "sshd", "vsftpd", "rpcbind")
    for needle in patterns:
        for pid, argv in _find_processes(needle):
            if argv:
                rows.append("%s (PID %s)" % (os.path.basename(argv[0]), pid))
    rows = sorted(set(rows), key=lambda value: value.lower())
    return "\n".join(rows) if rows else "No known GSU service processes detected."


def mount_information():
    rows = []
    network_types = ("nfs", "nfs4", "cifs", "smbfs")
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) >= 3 and fields[2].lower() in network_types:
            rows.append("%s\n  -> %s [%s]" % (fields[0], fields[1], fields[2]))
    return "\n\n".join(rows) if rows else "No active NFS/CIFS mounts."


def oscam_information():
    """Credential-safe runtime/config overview for the original OSCam information workflow."""
    rows = []
    matches = _find_processes("oscam")
    rows.append(_("Process: %s") % (_("RUNNING") if matches else _("not detected")))
    if matches:
        rows.append(_("Process IDs: %s") % ", ".join(pid for pid, argv in matches[:8]))
        executable = next((os.path.basename(argv[0]) for pid, argv in matches if argv), "")
        if executable:
            rows.append(_("Executable: %s") % executable)
    config_dir = _process_option(matches, "--config-dir")
    if not config_dir:
        for pidfile in ("/var/tmp/oscam-uni.pid", "/var/volatile/tmp/oscam-uni.pid"):
            if os.path.isfile(pidfile):
                rows.append(_("PID file: %s") % pidfile)
                break
    candidates = []
    if config_dir:
        candidates.append(os.path.join(config_dir, "oscam.conf"))
    candidates.extend(("/etc/tuxbox/config/oscam-uni/oscam.conf", "/etc/tuxbox/config/oscam.conf",
                       "/etc/tuxbox/config/oscam/oscam.conf", "/usr/keys/oscam.conf", "/var/keys/oscam.conf"))
    found = next((path for path in candidates if os.path.isfile(path)), "")
    rows += ["", _("Config: %s") % (found if found else _("not found"))]
    if config_dir:
        rows.append(_("Config dir: %s") % config_dir)
    if found:
        try:
            rows.append(_("Config size: %s") % _human_bytes(os.path.getsize(found)))
        except Exception:
            pass
    live, reason = oscam_live_rows() if matches else ([], "")
    rows += ["", _("Live client/reader rows: %d") % len(live)]
    if live:
        values = _oscam_table_values(live[0])
        rows += [_("Reader / User: %s") % (values["name"] or "N/A"),
                 _("Protocol: %s") % (values["protocol"] or "N/A"),
                 _("Channel: %s") % (values["channel"] or "N/A"),
                 _("ECM: %s") % (values["ecm"] or "N/A"),
                 _("Status: %s") % (values["status"] or "N/A")]
    elif reason:
        rows.append(reason)
    rows += ["", _("Credentials and raw configuration contents are never displayed.")]
    return "\n".join(rows)

def _proc_cmdline(pid):
    raw = _read_text("/proc/%s/cmdline" % pid, "")
    return [part for part in raw.split("\x00") if part]


def _find_processes(needle):
    rows = []
    try:
        pids = [name for name in os.listdir("/proc") if name.isdigit()]
    except Exception:
        pids = []
    for pid in pids:
        argv = _proc_cmdline(pid)
        if not argv:
            comm = _read_text("/proc/%s/comm" % pid, "")
            argv = [comm] if comm else []
        if argv and needle.lower() in " ".join(argv).lower():
            rows.append((pid, argv))
    return rows


def _process_option(matches, option):
    for pid, argv in matches:
        for index, value in enumerate(argv):
            if value == option and index + 1 < len(argv):
                return argv[index + 1]
            if value.startswith(option + "="):
                return value.split("=", 1)[1]
    return ""


def _parse_ini_section(path, section_name):
    values, current = {}, ""
    for raw in _read_lines(path):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            continue
        if current == section_name.lower() and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip().lower()] = value.strip()
    return values


def _oscam_webif_endpoint():
    """Return a safe local OSCam WebIF endpoint only when no WebIF auth is configured."""
    matches = _find_processes("oscam")
    config_dir = _process_option(matches, "--config-dir")
    candidates = []
    if config_dir:
        candidates.append(os.path.join(config_dir, "oscam.conf"))
    candidates += ["/etc/tuxbox/config/oscam-uni/oscam.conf",
                   "/etc/tuxbox/config/oscam.conf",
                   "/etc/tuxbox/config/oscam/oscam.conf"]
    conf = next((path for path in candidates if os.path.isfile(path)), "")
    if not conf:
        return "", "OSCam configuration not found."
    webif = _parse_ini_section(conf, "webif")
    raw_port = webif.get("httpport", "").strip()
    if not raw_port:
        return "", "OSCam WebIF is not configured."
    # Never obtain or use WebIF credentials. Authenticated WebIF remains read-only
    # from GSU's point of view until OSCam exposes a credential-free local API.
    if webif.get("httpuser") or webif.get("httppwd"):
        return "", "OSCam WebIF authentication is configured; live rows are not queried."
    ssl = raw_port.startswith("+")
    port = raw_port.lstrip("+")
    if not port.isdigit():
        return "", "OSCam WebIF port is invalid."
    scheme = "https" if ssl else "http"
    return "%s://127.0.0.1:%s" % (scheme, port), ""


def _oscam_live_status():
    """Fetch OSCam's local read-only status JSON without credentials."""
    endpoint, reason = _oscam_webif_endpoint()
    if not endpoint:
        return None, reason
    url = endpoint + "/oscamapi.json?part=status"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "GSU-Warder-Evolution"})
        with urllib.request.urlopen(request, timeout=2.0) as response:
            if response.getcode() != 200:
                return None, "OSCam WebIF returned HTTP %s." % response.getcode()
            raw = response.read(262145)
        if len(raw) > 262144:
            return None, "OSCam live status response is too large."
        return json.loads(raw.decode("utf-8", "replace")), ""
    except Exception as exc:
        return None, "OSCam live status unavailable: %s" % exc.__class__.__name__



_OSCAM_SAFE_SCHEMA_BLOCK = (
    "password", "passwd", "pwd", "token", "secret", "key", "boxkey",
    "deskey", "rsakey", "user", "username", "account"
)


def _oscam_safe_schema_paths(payload, limit=96):
    """Return OSCam JSON field paths only; never values or credential-like paths."""
    paths = []

    def walk(value, prefix="", depth=0):
        if depth > 6 or len(paths) >= limit:
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                name = str(key).lower()
                if any(block in name for block in _OSCAM_SAFE_SCHEMA_BLOCK):
                    continue
                path = ("%s.%s" % (prefix, name)) if prefix else name
                if path not in paths:
                    paths.append(path)
                walk(nested, path, depth + 1)
        elif isinstance(value, list):
            for item in value[:3]:
                walk(item, prefix + "[]" if prefix else "[]", depth + 1)

    walk(payload)
    return paths[:limit]


def oscam_api_schema_information():
    """Safe receiver-diagnostic view: field names/shape only, no OSCam values."""
    payload, reason = _oscam_live_status()
    if payload is None:
        return "OSCam API schema unavailable: %s" % reason
    paths = _oscam_safe_schema_paths(payload)
    if not paths:
        return "OSCam API reachable, but no safe schema paths were detected."
    return "OSCam API schema (field names only; values omitted)\n\n" + "\n".join(paths)


def _oscam_status_rows(payload):
    """Extract only actual OSCam client rows from known nested API containers."""
    found = []

    def add(value):
        if isinstance(value, dict) and value not in found and len(found) < 32:
            found.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item not in found and len(found) < 32:
                    found.append(item)

    def walk(value, depth=0):
        if depth > 7 or len(found) >= 32:
            return
        if isinstance(value, list):
            for item in value:
                walk(item, depth + 1)
            return
        if not isinstance(value, dict):
            return
        for key, nested in value.items():
            low = str(key).lower()
            if low in ("client", "clients") and isinstance(nested, (dict, list)):
                add(nested)
            elif isinstance(nested, (dict, list)):
                walk(nested, depth + 1)

    walk(payload)
    return found[:32]


def _oscam_scalar(value):
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return ""


def _oscam_pick(row, *names):
    for name in names:
        value = _oscam_scalar(row.get(name))
        if value:
            return value
    return "-"


def _oscam_client_type(row):
    raw = _oscam_pick(row, "type", "typ")
    mapping = {"s": "server", "h": "http", "p": "reader/proxy",
               "r": "reader", "c": "client"}
    return mapping.get(raw.lower(), raw)


def _oscam_flatten_scalars(value, prefix="", depth=0, out=None):
    """Flatten scalar OSCam API fields so variant builds can be mapped safely."""
    if out is None:
        out = {}
    if depth > 4:
        return out
    if isinstance(value, dict):
        for key, nested in value.items():
            name = str(key).lower()
            full = ("%s.%s" % (prefix, name)) if prefix else name
            _oscam_flatten_scalars(nested, full, depth + 1, out)
    elif isinstance(value, list):
        return out
    elif value not in (None, ""):
        text = str(value)
        out[prefix] = text
        leaf = prefix.rsplit(".", 1)[-1]
        out.setdefault(leaf, text)
    return out


def _oscam_flat_pick(flat, *names):
    for name in names:
        value = flat.get(name)
        if value not in (None, ""):
            return str(value)
    return "-"


def _oscam_find_scalar(flat, *tokens):
    """Find a scalar by exact leaf first, then conservative suffix/token matching."""
    direct = _oscam_flat_pick(flat, *tokens)
    if direct != "-":
        return direct
    wanted = tuple(token.lower() for token in tokens)
    for key, value in flat.items():
        low = key.lower()
        leaf = low.rsplit(".", 1)[-1]
        if leaf in wanted or any(low.endswith("." + token) for token in wanted):
            return str(value)
    return "-"


def _oscam_service_parts(flat):
    """Map common OSCam API service field spellings without exposing raw payloads."""
    return (
        _oscam_find_scalar(flat, "srvid", "serviceid", "service_id", "sid"),
        _oscam_find_scalar(flat, "caid"),
        _oscam_find_scalar(flat, "provid", "providerid", "provider_id", "prid"),
        _oscam_find_scalar(flat, "lastchannel", "channel", "channelname", "srvname", "servicename", "service_name", "service"),
    )


def _oscam_normalize_ecm(value):
    value = _oscam_display(value)
    if not value:
        return ""
    try:
        number = float(value)
        if number < 10:
            return "%d ms" % round(number * 1000)
        return "%d ms" % round(number)
    except Exception:
        return value


def _oscam_normalize_idle(value):
    value = _oscam_display(value)
    if not value:
        return ""
    try:
        seconds = int(float(value))
        if seconds < 60:
            return "%ds" % seconds
        if seconds < 3600:
            return "%dm%02ds" % (seconds // 60, seconds % 60)
        return "%dh%02dm" % (seconds // 3600, (seconds % 3600) // 60)
    except Exception:
        return value


def _oscam_row_is_noise(row):
    """Hide transport/WebIF infrastructure from the TV table, never from diagnostics."""
    typ = _oscam_display(row.get("type")).lower()
    protocol = _oscam_display(row.get("protocol")).lower()
    address = _oscam_display(row.get("address")).lower()
    name = _oscam_display(row.get("name")).lower()
    service = _oscam_service_display(row)
    status = _oscam_display(row.get("status"))
    if typ in ("http", "webif") or protocol in ("http", "https"):
        return True
    if typ == "server" and address in ("127.0.0.1", "::1", "localhost") and not service:
        return True
    if not any((name, service, status, protocol)) and not address:
        return True
    return False


def oscam_live_rows():
    """Return sanitized, display-ready OSCam client rows plus a status message."""
    payload, reason = _oscam_live_status()
    if payload is None:
        return [], reason
    rows = []
    seen = set()
    for item in _oscam_status_rows(payload):
        flat = _oscam_flatten_scalars(item)
        raw_type = _oscam_find_scalar(flat, "type", "typ")
        type_map = {"s": "server", "h": "http", "p": "proxy",
                    "r": "reader", "c": "client"}
        row_type = type_map.get(raw_type.lower(), raw_type)
        srvid, caid, provid, channel = _oscam_service_parts(flat)
        row = {
            "name": _oscam_find_scalar(flat, "name", "user", "label", "reader", "username"),
            "type": row_type,
            "address": _oscam_find_scalar(flat, "ip", "address", "host", "hostname", "remoteip", "remote_ip"),
            "port": _oscam_find_scalar(flat, "port", "remoteport", "remote_port"),
            "protocol": _oscam_find_scalar(flat, "protocol", "proto", "connectiontype", "connection_type"),
            "srvid": srvid,
            "caid": caid,
            "provid": provid,
            "channel": channel,
            "status": _oscam_find_scalar(flat, "status", "connection", "state", "connectionstatus", "connection_status"),
            "ecm": _oscam_normalize_ecm(_oscam_find_scalar(flat, "ecmtime", "ecm_time", "lastresponsetime", "lastresponse", "last_response")),
            "idle": _oscam_normalize_idle(_oscam_find_scalar(flat, "idle", "idletime", "idle_time")),
        }
        if not _oscam_row_is_noise(row):
            signature = tuple(_oscam_display(row.get(key)) for key in
                              ("name", "type", "address", "port", "protocol", "srvid", "caid",
                               "provid", "channel", "ecm", "idle", "status"))
            if signature not in seen:
                seen.add(signature)
                rows.append(row)
                if len(rows) >= 32:
                    break
    return rows, "" if rows else "API reachable, no useful client/reader rows recognized."


def _oscam_display(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("", "-", "n/a", "none", "null") else text


def _oscam_service_display(row):
    srvid, caid, provid = (_oscam_display(row.get(key)) for key in ("srvid", "caid", "provid"))
    if not any((srvid, caid, provid)):
        return ""
    return "%s:%s@%s" % (srvid or "----", caid or "----", provid or "------")


def _oscam_live_quality(rows):
    """Summarize whether the API mapping is useful without exposing row values."""
    if not rows:
        return "no rows"
    fields = ("name", "address", "port", "protocol", "srvid", "caid",
              "provid", "channel", "ecm", "idle", "status")
    useful = 0
    total = len(rows) * len(fields)
    for row in rows:
        useful += sum(1 for field in fields if _oscam_display(row.get(field)))
    percent = int(round((100.0 * useful) / total)) if total else 0
    return "%d/%d fields (%d%%)" % (useful, total, percent)


def _oscam_table_cell(value, width):
    value = str(value or "").replace("\n", " ").replace("\r", " ")
    if len(value) > width:
        value = value[:max(1, width - 1)] + "~"
    return value.ljust(width)


_OSCAM_COLUMNS = (
    ("name", 20, 165),
    ("address", 200, 190),
    ("port", 405, 75),
    ("protocol", 495, 130),
    ("service", 640, 225),
    ("channel", 880, 225),
    ("ecm", 1120, 95),
    ("idle", 1230, 80),
    ("status", 1325, 175),
)


def _oscam_row_role(row):
    typ = (row.get("type") or "").lower()
    name = (row.get("name") or "").lower()
    protocol = (row.get("protocol") or "").lower()
    address = _oscam_display(row.get("address"))
    if typ in ("reader", "proxy", "reader/proxy", "p") or "reader" in typ:
        return "R"
    if typ in ("client", "c") or "client" in typ:
        return "C"
    if typ in ("server", "s"):
        return "S"
    if typ in ("http", "h") or protocol == "http":
        return "W"
    if address in ("127.0.0.1", "::1") or name == "root":
        return "L"
    return " "


def _oscam_endpoint_display(row):
    address = _oscam_display(row.get("address"))
    port = _oscam_display(row.get("port"))
    if address and port:
        return "%s:%s" % (address, port)
    return address or port


def _oscam_name_display(row):
    name = _oscam_display(row.get("name"))
    if name:
        return name
    role = _oscam_row_role(row)
    protocol = _oscam_display(row.get("protocol")).lower()
    if protocol == "emu":
        return "EMU"
    if protocol == "dvbapi":
        return "DVBAPI"
    return {"R": "Reader", "C": "Client", "S": "Server", "L": "Local"}.get(role, "CAM")


def _oscam_status_display(row):
    status = _oscam_display(row.get("status"))
    if status:
        return status.upper()
    idle = _oscam_display(row.get("idle"))
    return "IDLE" if idle else ""


def _current_service_name():
    """Best-effort current Enigma2 service name; empty when unavailable."""
    try:
        from NavigationInstance import instance as navigation
        service = navigation and navigation.getCurrentService()
        info = service and service.info()
        name = info and info.getName()
        return _oscam_display(name)
    except Exception:
        return ""


def _oscam_row_channel(row):
    channel = _oscam_display(row.get("channel"))
    if channel:
        return channel
    # OSCam status often exposes SID/CAID but omits the human channel name.
    # Only DVBAPI/client rows represent the service currently watched by Enigma2.
    protocol = _oscam_display(row.get("protocol")).lower()
    role = _oscam_row_role(row)
    if protocol.startswith("dvbapi") or role == "C":
        return _current_service_name()
    return ""


def _oscam_table_values(row):
    name = _oscam_name_display(row)
    return {
        "name": name,
        "address": _oscam_display(row.get("address")),
        "port": _oscam_display(row.get("port")),
        "protocol": _oscam_display(row.get("protocol")),
        "service": _oscam_service_display(row),
        "channel": _oscam_row_channel(row),
        "ecm": _oscam_display(row.get("ecm")),
        "idle": _oscam_display(row.get("idle")),
        "status": _oscam_status_display(row),
    }


def _oscam_list_tuple(row):
    values = _oscam_table_values(row)
    return (row, values["name"], values["address"], values["port"], values["protocol"],
            values["service"], values["channel"], values["ecm"], values["idle"], values["status"])


def _oscam_multicontent_row(row):
    values = _oscam_table_values(row)
    if MultiContentEntryText is None:
        return _oscam_table_line(row)
    result = [row]
    for key, x, width in _OSCAM_COLUMNS:
        result.append(MultiContentEntryText(
            pos=(x, 0), size=(width, 34), font=0,
            flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
            text=values[key]))
    return result


def _oscam_table_line(row):
    values = _oscam_table_values(row)
    return " ".join((
        _oscam_table_cell(values["name"], 16),
        _oscam_table_cell(values["address"], 16),
        _oscam_table_cell(values["port"], 6),
        _oscam_table_cell(values["protocol"], 10),
        _oscam_table_cell(values["service"], 20),
        _oscam_table_cell(values["channel"], 24),
        _oscam_table_cell(values["ecm"], 9),
        _oscam_table_cell(values["idle"], 9),
        _oscam_table_cell(values["status"], 13),
    ))


def oscam_live_information():
    """Readable text fallback for Details/support output."""
    rows, reason = oscam_live_rows()
    if not rows:
        return "Live OSCam status: %s\nExisting CAM diagnostics remain available." % reason
    out = ["Live OSCam clients/readers", "",
           "Reader/User   Address         Port  Protocol   srvid:caid@provid      Channel              ECM      Idle     Status"]
    out.extend(_oscam_table_line(row) for row in rows)
    return "\n".join(out)


def oscam_webif_information():
    matches = _find_processes("oscam")
    config_dir = _process_option(matches, "--config-dir")
    candidates = []
    if config_dir:
        candidates.append(os.path.join(config_dir, "oscam.conf"))
    candidates += ["/etc/tuxbox/config/oscam-uni/oscam.conf",
                   "/etc/tuxbox/config/oscam.conf",
                   "/etc/tuxbox/config/oscam/oscam.conf"]
    conf = next((path for path in candidates if os.path.isfile(path)), "")
    if not conf:
        return "OSCam configuration not found."

    webif = _parse_ini_section(conf, "webif")
    port = webif.get("httpport", "disabled/not configured")
    bind = webif.get("httpip", "all interfaces")
    allowed = webif.get("httpallowed", "not restricted in config")
    user_set = bool(webif.get("httpuser"))
    pass_set = bool(webif.get("httppwd"))
    return "\n".join((
        "Config: %s" % conf,
        "",
        "WebIF port: %s" % port,
        "Bind: %s" % bind,
        "Allowed: %s" % allowed,
        "Authentication: %s" % ("configured" if user_set or pass_set else "not configured"),
        "",
        "Credentials are intentionally never displayed.",
    ))


def tuner_information():
    """Report tuner/front-end capabilities exposed by the running image."""
    rows = []
    nim_sockets = _read_lines("/proc/bus/nim_sockets")
    if nim_sockets:
        rows.append(_("Enigma2 tuner sockets"))
        rows.extend(line.rstrip() for line in nim_sockets[:80])
    else:
        rows.append(_("Enigma2 tuner socket table: not exposed"))

    frontend_roots = ("/proc/stb/frontend", "/sys/class/dvb")
    discovered = False
    for root in frontend_roots:
        try:
            entries = sorted(os.listdir(root))
        except Exception:
            entries = []
        if not entries:
            continue
        discovered = True
        rows += ["", "%s:" % root]
        for entry in entries[:32]:
            path = os.path.join(root, entry)
            if os.path.isdir(path):
                details = []
                try:
                    names = sorted(os.listdir(path))
                except Exception:
                    names = []
                for name in names:
                    candidate = os.path.join(path, name)
                    if not os.path.isfile(candidate):
                        continue
                    # Keep this page strictly read-only and bounded.  Only
                    # expose short text attributes; binary/control nodes are
                    # deliberately ignored.
                    value = _read_text(candidate, "")
                    if value and len(value) <= 160 and all(
                            ord(ch) >= 32 or ch in "\r\n\t" for ch in value):
                        value = " ".join(value.split())
                        if value:
                            details.append("%s=%s" % (name, value))
                    if len(details) >= 8:
                        break
                rows.append("%s%s" % (
                    entry, ("  " + ", ".join(details)) if details else ""))
            else:
                rows.append(entry)

    adapters = []
    try:
        adapters = sorted(name for name in os.listdir("/dev/dvb")
                          if name.startswith("adapter"))
    except Exception:
        pass
    rows += ["", _("DVB device adapters: %s") %
             (", ".join(adapters) if adapters else "not exposed")]

    if not nim_sockets and not discovered and not adapters:
        return "Tuner data not exposed through detected system interfaces."
    return "\n".join(rows)


def log_information():
    candidates = [
        "/home/root/logs/enigma2_crash.log",
        "/media/hdd/enigma2_crash.log",
        "/tmp/enigma2_crash.log",
        "/var/log/messages",
    ]
    rows = []
    for path in candidates:
        if os.path.isfile(path):
            try:
                stat = os.stat(path)
                rows.append("%s  (%.1f KiB)" % (path, stat.st_size / 1024.0))
            except Exception:
                rows.append(path)
    dmesg = _run(["dmesg"], 4)
    rows.append(_("Kernel log: %s") % (_("available") if dmesg else _("not available")))
    return "\n".join(rows) if rows else "No known diagnostic logs found."


def _redact_diagnostic_text(text):
    """Redact credentials, cryptographic secrets and stable private identifiers."""
    # Diagnostic identifiers such as interface MAC addresses remain visible;
    # they are useful for support and are not authentication secrets.
    value = text or ""
    rules = (
        (r"(?im)^((?:user|username|password|passwd|pwd|httpuser|httppwd|rsakey|boxkey|deskey|key)\s*[=:]\s*).*$", r"\1<redacted>"),
        (r"(?i)\b(?:serial(?:_number)?|uuid|machine-id)\s*[=:]\s*[^\s]+", "<redacted-identifier>"),
    )
    for pattern, replacement in rules:
        value = re.sub(pattern, replacement, value)
    return value

def _safe_diagnostic_file(path, limit=131072):
    try:
        if not os.path.isfile(path):
            return ""
        with open(path, "rb") as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit or b"\x00" in raw:
            return ""
        return _redact_diagnostic_text(raw.decode("utf-8", "replace"))
    except Exception:
        return ""



def health_check_information():
    """Build a conservative, read-only health overview from exposed capabilities."""
    rows = [_("GSU Health Check"), ""]

    # Memory pressure: MemAvailable is more useful than MemFree on Linux.
    mem = {}
    for line in _read_lines("/proc/meminfo"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields = value.split()
        if fields and fields[0].isdigit():
            mem[key] = int(fields[0])
    total = mem.get("MemTotal", 0)
    available = mem.get("MemAvailable", mem.get("MemFree", 0))
    if total:
        pct = available * 100.0 / total
        state = "PASS" if pct >= 15 else ("WARNING" if pct >= 7 else "WARNING")
        rows.append(_("[%s] Memory: %.0f%% available") % (state, pct))
    else:
        rows.append(_("[INFO] Memory: data not exposed"))

    # Filesystems: warn only about mounted physical filesystems that are genuinely tight.
    storage_seen = False
    storage_warning = False
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) < 3 or not fields[0].startswith("/dev/"):
            continue
        storage_seen = True
        try:
            usage = shutil.disk_usage(fields[1])
            free_pct = usage.free * 100.0 / usage.total if usage.total else 100.0
            if free_pct < 5:
                storage_warning = True
        except Exception:
            pass
    if storage_seen:
        rows.append("[%s] Storage: %s" % (
            "WARNING" if storage_warning else "PASS",
            "one or more filesystems below 5% free" if storage_warning else "mounted filesystems have usable free space"))
    else:
        rows.append(_("[INFO] Storage: no physical filesystem mounts detected"))

    # Network capability/state. Loopback is deliberately ignored.
    interfaces = []
    try:
        interfaces = [name for name in sorted(os.listdir("/sys/class/net")) if name != "lo"]
    except Exception:
        pass
    up = [name for name in interfaces if _read_text("/sys/class/net/%s/operstate" % name, "") == "up"]
    gateway = _default_gateway()
    resolvers = [line.split()[1] for line in _read_lines("/etc/resolv.conf")
                 if len(line.split()) >= 2 and line.split()[0] == "nameserver"]
    if up:
        rows.append(_("[PASS] Network link: %s") % ", ".join(up))
    elif interfaces:
        rows.append(_("[WARNING] Network link: no detected interface is up"))
    else:
        rows.append(_("[INFO] Network link: interfaces not exposed"))
    rows.append(_("[%s] Default gateway: %s") % ("PASS" if gateway and gateway != "N/A" else "INFO", gateway or "N/A"))
    rows.append(_("[%s] DNS configuration: %s") % (
        "PASS" if resolvers else "WARNING", ", ".join(resolvers) if resolvers else "no resolver configured"))

    # Enigma2 is expected while this screen is running; report rather than mutate anything.
    e2 = _find_processes("enigma2")
    rows.append(_("[%s] Enigma2 process: %s") % ("PASS" if e2 else "WARNING", _("running") if e2 else _("not detected")))

    temps = _temperature_values()
    if temps:
        hottest = max(value for label, value in temps)
        state = "PASS" if hottest < 80 else ("WARNING" if hottest < 95 else "WARNING")
        rows.append(_("[%s] Temperature: hottest detected %.1f C") % (state, hottest))
    else:
        rows.append(_("[INFO] Temperature: measurement not exposed"))

    mounts = [line for line in _read_lines("/proc/mounts")
              if len(line.split()) >= 3 and line.split()[2].lower() in ("nfs", "nfs4", "cifs", "smbfs")]
    rows.append(_("[INFO] Network mounts: %d active") % len(mounts))

    cams = []
    for name in ("oscam", "ncam", "cccam", "mgcamd"):
        if _find_processes(name):
            cams.append(name)
    rows.append(_("[INFO] CAM: %s") % (", ".join(sorted(set(cams))) if cams else _("no known CAM process detected")))

    nim = _read_lines("/proc/bus/nim_sockets")
    try:
        dvb = sorted(os.listdir("/sys/class/dvb"))
    except Exception:
        dvb = []
    if nim or dvb:
        rows.append(_("[PASS] Tuner interfaces: detected"))
    else:
        rows.append(_("[INFO] Tuner interfaces: not exposed through detected system interfaces"))

    rows += ["", _("Health Check is read-only. INFO means a capability is absent, optional, or not enough evidence exists to call it a fault.")]
    return "\n".join(rows)

def create_diagnostic_bundle():
    """Create a bounded, redacted support bundle without changing system state."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = "/tmp/gsu-diagnostics-%s.tar.gz" % stamp
    workspace = tempfile.mkdtemp(prefix="gsu-diagnostics-")
    try:
        reports = {
            "summary.txt": diagnostic_summary(),
            "system.txt": system_information(),
            "hardware.txt": hardware_identity_information(),
            "network.txt": network_information(),
            "storage.txt": storage_information(),
            "memory.txt": memory_information(),
            "services.txt": service_information(),
            "mounts.txt": mount_information(),
            "tuners.txt": tuner_information(),
            "temperatures.txt": temperature_information(),
            "capabilities.txt": capability_information(),
            "image-runtime.txt": image_information(),
            "packages.txt": package_information(),
            "oscam-status.txt": oscam_information(),
        }
        active = _active_cam()
        if active and active.get("family") == "oscam":
            reports["oscam-api-schema.txt"] = oscam_api_schema_information()
        for name, report in reports.items():
            with open(os.path.join(workspace, name), "w") as handle:
                handle.write(_redact_diagnostic_text(report) + "\n")

        # Include only bounded text logs.  OSCam configuration/account files
        # are intentionally never copied into a support bundle.
        log_paths = (
            "/home/root/logs/enigma2_crash.log",
            "/media/hdd/enigma2_crash.log",
            "/tmp/enigma2_crash.log",
            "/var/log/messages",
        )
        for index, path in enumerate(log_paths):
            data = _safe_diagnostic_file(path)
            if data:
                with open(os.path.join(workspace, "log-%02d.txt" % index), "w") as handle:
                    handle.write("Source: %s\n\n%s" % (path, data))

        manifest = (
            "Glass System Utility - Warder Evolution diagnostic bundle\n"
            "GSU version: %s\n"
            "Generated: %s\n"
            "Privacy: credentials and stable identifiers are redacted; diagnostic LAN/MAC data is preserved; "
            "CAM account/configuration files are excluded.\n"
        ) % (VERSION, time.strftime("%Y-%m-%d %H:%M:%S"))
        with open(os.path.join(workspace, "README.txt"), "w") as handle:
            handle.write(manifest)

        with tarfile.open(target, "w:gz") as archive:
            for name in sorted(os.listdir(workspace)):
                archive.add(os.path.join(workspace, name), arcname=name, recursive=False)
        return target
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _temperature_candidates():
    """Discover temperature interfaces by capability, not receiver brand."""
    candidates = []

    # Linux thermal class. Entries are commonly symlinks, so enumerate them
    # explicitly instead of relying on os.walk() following directory links.
    thermal_root = "/sys/class/thermal"
    try:
        for name in sorted(os.listdir(thermal_root)):
            if name.startswith("thermal_zone"):
                candidates.append((os.path.join(thermal_root, name, "temp"),
                                   os.path.join(thermal_root, name, "type")))
    except Exception:
        pass

    # Generic Linux hwmon interfaces.
    hwmon_root = "/sys/class/hwmon"
    try:
        for hwmon in sorted(os.listdir(hwmon_root)):
            base = os.path.join(hwmon_root, hwmon)
            try:
                for name in sorted(os.listdir(base)):
                    if name.startswith("temp") and name.endswith("_input"):
                        stem = name[:-6]
                        candidates.append((os.path.join(base, name),
                                           os.path.join(base, stem + "_label")))
            except Exception:
                pass
    except Exception:
        pass

    # Enigma2/STB compatibility interfaces. These are capability probes only;
    # no receiver brand/model assumptions are made.
    candidates.extend([
        ("/proc/stb/sensors/temp0/value", ""),
        ("/proc/stb/fp/temp_sensor", ""),
    ])
    return candidates


def _temperature_values():
    """Return valid readings from detected sysfs and Enigma2 sensor files."""
    values = []
    seen = set()
    for path, label_path in _temperature_candidates():
        if not os.path.isfile(path):
            continue
        try:
            raw = _read_text(path, "")
            value = float(raw)
            if abs(value) >= 1000:
                value /= 1000.0
            if not (-20.0 <= value <= 150.0):
                continue
            real = os.path.realpath(path)
            if real in seen:
                continue
            seen.add(real)
            label = _read_text(label_path, "") if label_path else ""
            if not label:
                parent = os.path.basename(os.path.dirname(path))
                label = parent if parent else "Temperature"
            values.append((label, value))
        except Exception:
            pass
    return values


def temperature_information():
    rows = ["%s: %.1f C" % (label, value) for label, value in _temperature_values()]
    if rows:
        return "\n".join(rows)
    return "Temperature data not exposed through detected system interfaces."


def _active_cam():
    """Return a conservative description of the active CAM process."""
    for needle in ("oscam", "ncam", "cccam", "mgcamd"):
        matches = _find_processes(needle)
        if matches:
            pid, argv = matches[0]
            binary = os.path.basename(argv[0]) if argv else needle
            return {"family": needle, "name": binary, "pid": pid, "matches": matches}
    return None



def _process_runtime_seconds(pid):
    """Read process age from /proc/<pid>/stat and system uptime."""
    try:
        stat = _read_text("/proc/%s/stat" % pid, "")
        end = stat.rfind(")")
        fields = stat[end + 2:].split()
        # field 22 (starttime) becomes index 19 after removing pid/comm.
        start_ticks = int(fields[19])
        ticks = os.sysconf("SC_CLK_TCK")
        uptime = float(_read_text("/proc/uptime", "0").split()[0])
        return max(0, int(uptime - (start_ticks / float(ticks))))
    except Exception:
        return None


def _cam_process_metrics(pid):
    rows = []
    status = {}
    for line in _read_lines("/proc/%s/status" % pid):
        if ":" in line:
            key, value = line.split(":", 1)
            status[key.strip()] = value.strip()
    if status.get("VmRSS"):
        rows.append(_("Resident memory: %s") % status["VmRSS"])
    if status.get("VmSize"):
        rows.append(_("Virtual memory: %s") % status["VmSize"])
    seconds = _process_runtime_seconds(pid)
    if seconds is not None:
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        rows.append(_("Process runtime: %dd %02d:%02d:%02d") % (days, hours, minutes, seconds))
    return rows

def active_cam_summary():
    cam = _active_cam()
    if not cam:
        return "No known active CAM process detected."
    rows = [
        _("Active CAM: %s") % cam["name"],
        _("Family: %s") % cam["family"],
        "PID: %s" % cam["pid"],
    ]
    rows.extend(_cam_process_metrics(cam["pid"]))
    return "\n".join(rows)


def active_cam_information():
    cam = _active_cam()
    if not cam:
        return "No known active CAM process detected."
    rows = [active_cam_summary()]
    if cam["family"] == "oscam":
        rows += ["", oscam_runtime_information(), "", oscam_webif_information()]
    return "\n".join(rows)




def _percent_bar(value, width=18):
    try:
        value = max(0, min(100, int(float(value))))
    except Exception:
        return "[" + ("-" * width) + "]"
    filled = int(round((value / 100.0) * width))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "] %d%%" % value


def original_resource_dashboard_information():
    """Compact GSU-style resource meters with original RAM/Swap/Root facts."""
    rows = []
    try:
        mem = {}
        with open("/proc/meminfo", "r") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                mem[key] = int(value.strip().split()[0])
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        used = max(0, total - avail)
        used_pct = int(round(100.0 * used / total)) if total else 0
        rows.append("RAM   " + _percent_bar(used_pct))
        if total:
            rows.append("      %.1f / %.1f MiB" % (used / 1024.0, total / 1024.0))
        stotal = mem.get("SwapTotal", 0)
        sfree = mem.get("SwapFree", 0)
        sused = max(0, stotal - sfree)
        swap_pct = int(round(100.0 * sused / stotal)) if stotal else 0
        rows.append("Swap  " + _percent_bar(swap_pct))
        rows.append("      %.1f / %.1f MiB" % (sused / 1024.0, stotal / 1024.0))
    except Exception:
        rows += ["RAM   " + _percent_bar(None), "Swap  " + _percent_bar(None)]
    try:
        stat = os.statvfs("/")
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = max(0, total - free)
        root_pct = int(round(100.0 * used / total)) if total else 0
        rows.append("Root  " + _percent_bar(root_pct))
        rows.append("      %s / %s" % (_human_bytes(used), _human_bytes(total)))
    except Exception:
        rows.append("Root  " + _percent_bar(None))
    temps = _temperature_values()
    if temps:
        hottest = max(value for _name, value in temps)
        rows += ["", _("Temperature: %.1f C") % hottest]
    return "\n".join(rows)

def original_protocol_indicators():
    """Original-style service indicators backed by process/listener discovery."""
    names = []
    for needle in ("vsftpd", "proftpd", "pure-ftpd", "telnetd", "openvpn", "wireguard", "wg-quick", "smbd", "nmbd", "nfsd", "rpc.mountd"):
        if _find_processes(needle):
            names.append(needle)
    names = " ".join(names)
    mapping = (("FTP", ("vsftpd", "proftpd", "pure-ftpd")),
               ("Telnet", ("telnetd",)),
               ("VPN", ("openvpn", "wireguard", "wg-quick")),
               ("Samba", ("smbd", "nmbd")),
               ("NFS", ("nfsd", "rpc.mountd")))
    return "   ".join("%s:%s" % (label, "ON" if any(x in names for x in needles) else "--")
                    for label, needles in mapping)



def _format_orbital_position(value):
    try:
        value = int(value)
        if value > 1800:
            return "%.1fW" % ((3600 - value) / 10.0)
        return "%.1fE" % (value / 10.0)
    except Exception:
        return str(value) if value not in (None, "") else _("not exposed")


def _format_frontend_frequency(value):
    try:
        value = int(value)
        # Enigma2 DVB frontend data normally exposes kHz; keep unusual values explicit.
        return "%.3f MHz" % (value / 1000.0) if value >= 100000 else str(value)
    except Exception:
        return str(value) if value not in (None, "") else _("not exposed")


def _format_symbol_rate(value):
    try:
        value = int(value)
        return "%d kSym/s" % (value // 1000) if value >= 100000 else str(value)
    except Exception:
        return str(value) if value not in (None, "") else _("not exposed")


def cam_srv_context_information():
    """Original GSU CAM/SRV context assembled without exposing secrets."""
    cam = _active_cam()
    service = current_service_technical_information()
    rows = []
    rows.append(_("Active CAM: %s") % (cam["name"] if cam else _("None")))
    rows.append(_("CAM family: %s") % (cam["family"] if cam else _("N/A")))
    rows.append(_("Service: %s") % (service.get("name") or _("not exposed")))
    rows.append(_("Provider: %s") % (service.get("provider") or _("not exposed")))
    fe = service.get("frontend") or {}
    orbital = fe.get("orbital_position")
    if orbital not in (None, ""):
        rows.append(_("Orbital position: %s") % _format_orbital_position(orbital))
    caids = service.get("caids") or []
    rows.append(_("Available CAIDs: %s") % (
        ", ".join("%04X" % value for value in caids) if caids else _("not exposed")))
    return "\n".join(rows)


def _active_cam_restart_command():
    """Discover an image-provided restart path; never fall back to killall."""
    cam = _active_cam()
    if not cam:
        return None, "No active CAM detected."

    name = cam["name"]
    candidates = [
        ("/etc/init.d/softcam.%s" % name, ["/etc/init.d/softcam.%s" % name, "restart"]),
        ("/etc/init.d/%s" % name, ["/etc/init.d/%s" % name, "restart"]),
        ("/etc/init.d/softcam", ["/etc/init.d/softcam", "restart"]),
    ]
    for path, argv in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return argv, "Restart %s using %s" % (name, path)
    return None, "No safe image-provided restart mechanism detected for %s." % name

def oscam_runtime_information():
    rows = []
    version_files = (
        "/var/volatile/tmp/.oscam/oscam.version",
        "/var/tmp/.oscam/oscam.version",
        "/tmp/.oscam/oscam.version",
    )
    version_file = next((path for path in version_files if os.path.isfile(path)), "")
    if version_file:
        rows.append(_("Runtime version file: %s") % version_file)
        for line in _read_lines(version_file)[:30]:
            text = line.strip()
            if text and not any(secret in text.lower() for secret in ("password", "passwd", "pwd=")):
                rows.append(text)
    else:
        rows.append(_("OSCam runtime version file: not found"))

    matches = _find_processes("oscam")
    config_dir = _process_option(matches, "--config-dir")
    if config_dir:
        server = os.path.join(config_dir, "oscam.server")
        users = os.path.join(config_dir, "oscam.user")
        reader_count = sum(1 for line in _read_lines(server) if line.strip().lower() == "[reader]")
        user_count = sum(1 for line in _read_lines(users) if line.strip().lower() in ("[account]", "[user]"))
        rows += ["", _("Readers configured: %d") % reader_count, _("Accounts configured: %d") % user_count]
    return "\n".join(rows)


def package_information():
    rows = []
    for package in ("enigma2", "enigma2-plugin-glasssysutil"):
        output = _run(["opkg", "status", package], 5)
        version = ""
        status = ""
        for line in output.splitlines():
            if line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
            elif line.startswith("Status:"):
                status = line.split(":", 1)[1].strip()
        rows.append("%s" % package)
        rows.append(_("Version: %s") % (version or _("N/A")))
        rows.append(_("Status: %s") % (status or _("N/A")))
    rows += ["", _("Available upgrades: not checked here (repository queries may block this screen).")]
    return "\n".join(rows)


def network_health_information():
    """Fast read-only network health focused on link, addressing, gateway and DNS."""
    rows = [_("GSU Network Health"), ""]
    try:
        names = sorted(name for name in os.listdir("/sys/class/net") if name != "lo")
    except Exception:
        names = []
    up = []
    addressed = []
    for name in names:
        state = _read_text("/sys/class/net/%s/operstate" % name, "unknown")
        ipv4 = _ipv4_for_interface(name)
        if state == "up":
            up.append(name)
        if ipv4 != "N/A":
            addressed.append("%s=%s" % (name, ipv4))
        rows.append("[%s] %-10s link=%s  IPv4=%s" % (
            "PASS" if state == "up" else "INFO", name, state, ipv4))
    if not names:
        rows.append(_("[INFO] Network interfaces not exposed."))

    gateway = _default_gateway()
    if gateway != "N/A":
        rc, output = _run_status(["ping", "-c", "1", "-W", "2", gateway], 4)
        rows.append("[%s] Gateway %s  %s" % (
            "PASS" if rc == 0 else "WARNING", gateway,
            "reachable" if rc == 0 else "no ping reply"))
    else:
        rows.append(_("[WARNING] Default gateway not detected."))

    resolvers = []
    for line in _read_lines("/etc/resolv.conf"):
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "nameserver":
            resolvers.append(fields[1])
    rows.append("[%s] DNS resolver configuration: %s" % (
        "PASS" if resolvers else "WARNING",
        ", ".join(resolvers) if resolvers else "none detected"))
    rows += ["", _("Summary: %d interface(s) up, %d with IPv4.") % (len(up), len(addressed)),
             _("Network Health is read-only; ping failure alone is reported as a warning, not proof of link failure.")]
    return "\n".join(rows)


def network_diagnostics():
    rows = []
    gateway = _default_gateway()
    rows.append(_("Default gateway: %s") % gateway)
    if gateway != "N/A":
        rc, ping = _run_status(["ping", "-c", "1", "-W", "2", gateway], 4)
        rows.append(_("Gateway reachability: %s") % ("OK" if rc == 0 else _("no reply")))

    resolvers = []
    for line in _read_lines("/etc/resolv.conf"):
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "nameserver":
            resolvers.append(fields[1])
    rows.append(_("DNS servers: %s") % (", ".join(resolvers) if resolvers else _("N/A")))

    route = _run(["ip", "route"], 4)
    if route:
        rows += ["", _("Routes:")]
        rows.extend(route.splitlines()[:20])
    return "\n".join(rows)



def network_mount_doctor_information():
    """Read-only NFS/CIFS doctor for active mounts and common client capabilities."""
    rows = [_("GSU Network Mount Doctor"), ""]
    active = []
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) < 4 or fields[2].lower() not in ("nfs", "nfs4", "cifs", "smbfs"):
            continue
        source, target, fstype, options = fields[:4]
        active.append((source, target, fstype, options))
        try:
            usage = shutil.disk_usage(target)
            free_pct = usage.free * 100.0 / usage.total if usage.total else 0
            state = "PASS" if free_pct >= 5 else "WARNING"
            rows.append("[%s] %s -> %s [%s] %.1f%% free" % (state, source, target, fstype, free_pct))
        except Exception:
            rows.append(_("[INFO] %s -> %s [%s] mounted; usage unavailable") % (source, target, fstype))
    if not active:
        rows.append(_("[INFO] No active NFS/CIFS mounts."))

    rows += ["", _("Client capabilities:")]
    nfs = bool(shutil.which("mount.nfs") or shutil.which("mount.nfs4") or os.path.exists("/sbin/mount.nfs"))
    cifs = bool(shutil.which("mount.cifs") or os.path.exists("/sbin/mount.cifs"))
    rows.append(_("NFS client: %s") % (_("available") if nfs else _("not detected")))
    rows.append(_("CIFS client: %s") % (_("available") if cifs else _("not detected")))

    files = [path for path in ("/etc/fstab", "/etc/enigma2/automounts.xml", "/etc/auto.network")
             if os.path.isfile(path)]
    rows.append(_("Persistent mount configuration: %s") % (", ".join(files) if files else _("not detected")))
    rows += ["", _("Doctor is read-only; credentials and mount configuration values are not displayed.")]
    return "\n".join(rows)


def time_health_information():
    """Report clock and detected time-sync facilities without assuming an image."""
    rows = [_("Local time: %s") % time.strftime("%Y-%m-%d %H:%M:%S %Z")]
    rows.append(_("UTC time: %s") % time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

    detected = []
    for name in ("chronyd", "ntpd", "ntpdate", "systemd-timesyncd"):
        matches = _find_processes(name)
        if matches:
            detected.append("%s (running)" % name)
    for binary in ("chronyc", "ntpq", "timedatectl"):
        path = _run(["which", binary], 2)
        if path:
            detected.append("%s (available)" % binary)
    rows.append(_("Time sync: %s") % (", ".join(detected) if detected else _("no known time-sync facility detected")))

    # Prefer status commands only when the corresponding client exists.
    chronyc = _run(["which", "chronyc"], 2)
    if chronyc:
        tracking = _run(["chronyc", "tracking"], 4)
        if tracking:
            rows += ["", _("chrony tracking:")]
            rows.extend(tracking.splitlines()[:16])
    else:
        ntpq = _run(["which", "ntpq"], 2)
        if ntpq:
            peers = _run(["ntpq", "-pn"], 4)
            if peers:
                rows += ["", _("NTP peers:")]
                rows.extend(peers.splitlines()[:16])
    return "\n".join(rows)

def runtime_health_information():
    """Compact Enigma2 runtime health without duplicating process/log screens."""
    rows = [_("GSU Enigma2 Runtime Health"), ""]
    matches = _find_processes("enigma2")
    if not matches:
        rows.append(_("[WARNING] Enigma2 process not detected."))
        return "\n".join(rows)
    pid = matches[0][0]
    rows.append(_("[PASS] Enigma2 running  PID %s") % pid)
    status = {}
    for line in _read_lines("/proc/%s/status" % pid):
        if ":" in line:
            key, value = line.split(":", 1)
            status[key] = value.strip()
    for key, label in (("VmRSS", "Resident memory"), ("VmSize", "Virtual memory"), ("Threads", "Threads")):
        if status.get(key):
            rows.append("[INFO] %s: %s" % (label, status[key]))
    fd_path = "/proc/%s/fd" % pid
    try:
        rows.append(_("[INFO] Open file descriptors: %d") % len(os.listdir(fd_path)))
    except Exception:
        rows.append(_("[INFO] Open file descriptors: not exposed"))
    crash_logs = []
    for path in ("/home/root/logs/enigma2_crash.log", "/media/hdd/enigma2_crash.log", "/tmp/enigma2_crash.log"):
        if os.path.isfile(path):
            try:
                crash_logs.append("%s (%.1f KiB)" % (path, os.stat(path).st_size / 1024.0))
            except Exception:
                crash_logs.append(path)
    rows.append(_("[%s] Known crash logs: %d") % ("INFO" if crash_logs else "PASS", len(crash_logs)))
    rows.extend("       %s" % item for item in crash_logs[:3])
    rows += ["", _("Runtime Health is read-only; it does not restart Enigma2 or delete logs.")]
    return "\n".join(rows)


def device_information():
    rows = []
    block_root = "/sys/class/block"
    try:
        devices = sorted(os.listdir(block_root))
    except Exception:
        devices = []
    for name in devices:
        if name.startswith(("loop", "ram", "mtdblock")):
            continue
        base = os.path.join(block_root, name)
        size_raw = _read_text(os.path.join(base, "size"), "0")
        try:
            gib = int(size_raw) * 512.0 / 1073741824.0
        except Exception:
            gib = 0
        model = _read_text(os.path.join(base, "device/model"), "")
        removable = _read_text(os.path.join(base, "removable"), "0")
        rows.append("%s  %.1f GiB%s%s" % (
            name, gib,
            "  removable" if removable == "1" else "",
            "  %s" % model if model else ""))
    return "\n".join(rows) if rows else "No block devices exposed by this image."


def image_information():
    rows = []
    files = ("/etc/image-version", "/etc/issue", "/etc/os-release")
    for path in files:
        if os.path.isfile(path):
            rows.append(path)
            for line in _read_lines(path)[:20]:
                text = line.strip()
                if text:
                    rows.append("  %s" % text)
            rows.append("")
    rows.append(_("Enigma2 binary: %s") % (_run(["which", "enigma2"], 3) or _("not found")))
    rows.append(_("Python: %s") % platform.python_version())
    return "\n".join(rows)


def cam_inventory_information():
    rows = []
    init_root = "/etc/init.d"
    try:
        names = sorted(name for name in os.listdir(init_root) if "softcam" in name.lower() or "cam" in name.lower())
    except Exception:
        names = []
    if names:
        rows.append(_("Init scripts:"))
        rows.extend("  %s" % name for name in names[:30])

    binaries = []
    for root in ("/usr/bin", "/usr/softcams", "/var/bin"):
        if not os.path.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                low = name.lower()
                if any(token in low for token in ("oscam", "ncam", "cccam", "mgcam")):
                    path = os.path.join(root, name)
                    if os.path.isfile(path):
                        binaries.append(path)
        except Exception:
            pass
    if binaries:
        rows += ["", _("Detected CAM binaries:")]
        rows.extend("  %s" % path for path in sorted(set(binaries))[:40])
    return "\n".join(rows) if rows else "No known CAM components detected."


def service_dashboard_information():
    """Compact operational dashboard for services users actually troubleshoot."""
    rows = [_("GSU Service Dashboard"), ""]
    e2 = _find_processes("enigma2")
    rows.append("[%-7s] Enigma2  %s" % ("RUNNING" if e2 else "DOWN",
                ("PID " + ", ".join(str(pid) for pid, cmd in e2[:3])) if e2 else "not detected"))
    cam = _active_cam()
    if cam:
        # _active_cam() returns the shared capability record used by the
        # OSCam monitor, not the legacy (name, matches) tuple.
        name = cam.get("name") or cam.get("family") or "unknown"
        matches = cam.get("matches") or []
        pids = [str(pid) for pid, cmd in matches[:3]]
        if not pids and cam.get("pid") is not None:
            pids = [str(cam["pid"])]
        rows.append("[RUNNING] CAM       %s  PID %s" % (name, ", ".join(pids) if pids else "not exposed"))
    else:
        rows.append(_("[INFO   ] CAM       no known CAM process detected"))
    sync = [name for name in ("chronyd", "ntpd", "systemd-timesyncd") if _find_processes(name)]
    rows.append("[%-7s] Time sync %s" % ("RUNNING" if sync else "INFO",
                ", ".join(sync) if sync else "no known daemon detected"))
    mounts = []
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) >= 3 and fields[2].lower() in ("nfs", "nfs4", "cifs", "smbfs"):
            mounts.append("%s -> %s (%s)" % (fields[0], fields[1], fields[2]))
    rows.append(_("[INFO   ] Net mounts %d active") % len(mounts))
    rows.extend("           %s" % item for item in mounts[:6])
    listeners = _run(["ss", "-lntup"], 4) or _run(["netstat", "-lntup"], 4)
    count = max(0, len(listeners.splitlines()) - 1) if listeners else 0
    rows.append(_("[INFO   ] Listeners  %d detected") % count)
    rows += ["", _("Dashboard is read-only. Use dedicated screens for full diagnostics.")]
    return "\n".join(rows)


def listening_ports_information():
    output = _run(["ss", "-lntup"], 5) or _run(["netstat", "-lntup"], 5)
    return "\n".join(output.splitlines()[:45]) if output else "No listener information available."


def storage_health_information():
    """Concise storage health view focused on actionable receiver conditions."""
    rows = [_("GSU Storage Health"), ""]
    seen = 0
    warnings = 0
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) < 4 or not fields[0].startswith("/dev/"):
            continue
        device, mountpoint, fstype, options = fields[:4]
        try:
            usage = shutil.disk_usage(mountpoint)
            free_pct = usage.free * 100.0 / usage.total if usage.total else 0
        except Exception:
            continue
        seen += 1
        read_only = "ro" in options.split(",")
        low_space = free_pct < 5
        if read_only or low_space:
            warnings += 1
        state = "WARNING" if (read_only or low_space) else "PASS"
        notes = []
        if read_only:
            notes.append("read-only")
        if low_space:
            notes.append("low free space")
        rows.append("[%s] %s -> %s  %s  %.1f%% free%s" % (
            state, device, mountpoint, fstype, free_pct,
            ("  " + ", ".join(notes)) if notes else ""))
    if not seen:
        rows.append(_("[INFO] No physical mounted filesystems detected."))
    rows += ["", _("Summary: %d filesystem(s), %d warning(s).") % (seen, warnings),
             _("Storage Health is read-only and does not run destructive filesystem tests.")]
    return "\n".join(rows)


def filesystem_health_information():
    rows = []
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) < 4 or not fields[0].startswith("/dev/"):
            continue
        device, mountpoint, fstype, options = fields[:4]
        state = "read-only" if "ro" in options.split(",") else "read-write"
        try:
            usage = shutil.disk_usage(mountpoint)
            free_pct = usage.free * 100.0 / usage.total if usage.total else 0
            rows.append("%s -> %s [%s, %s] free %.1f%%" % (device, mountpoint, fstype, state, free_pct))
        except Exception:
            rows.append("%s -> %s [%s, %s]" % (device, mountpoint, fstype, state))
    return "\n".join(rows) if rows else "No physical filesystems found."


def capability_information():
    """Report interfaces actually exposed by the running receiver/image."""
    temp_paths = [path for path, label in _temperature_candidates() if os.path.isfile(path)]
    probes = [
        ("Temperature interfaces", bool(temp_paths)),
        ("Temperature readings", bool(_temperature_values())),
        ("Thermal sysfs", os.path.isdir("/sys/class/thermal")),
        ("Hardware monitor", os.path.isdir("/sys/class/hwmon")),
        ("Network sysfs", os.path.isdir("/sys/class/net")),
        ("Block sysfs", os.path.isdir("/sys/class/block")),
        ("Tuner procfs", os.path.exists("/proc/bus/nim_sockets") or os.path.isdir("/proc/stb/frontend")),
        ("Enigma2 STB procfs", os.path.isdir("/proc/stb")),
        ("Mount table", os.path.isfile("/proc/mounts")),
        ("opkg", bool(shutil.which("opkg"))),
        ("iproute2", bool(shutil.which("ip"))),
        ("ss/netstat", bool(shutil.which("ss") or shutil.which("netstat"))),
        ("pgrep", bool(shutil.which("pgrep"))),
    ]
    rows = [_("Detected runtime capabilities"), ""]
    rows.extend("%-20s %s" % (name + ":", "YES" if present else "no") for name, present in probes)
    return "\n".join(rows)



def original_system_overview_information():
    """GSU-style consolidated system overview backed by modern read-only probes."""
    sections = [
        (_("System & Hardware"), system_information()),
        (_("Memory & Swap"), memory_information()),
        (_("Temperatures"), temperature_information()),
        (_("Storage & Filesystems"), storage_health_information()),
        (_("Services & Processes"), service_dashboard_information()),
    ]
    rows = [_("GSU System Information"), "=" * 54]
    for title, body in sections:
        rows += ["", "[ %s ]" % title, body]
    return "\n".join(rows)



def current_service_technical_information():
    """Best-effort live service/transponder data through current Enigma2 APIs."""
    data = {"name": _current_service_name(), "provider": "", "reference": "", "frontend": {},
            "pids": {}, "caids": []}
    try:
        from NavigationInstance import instance as navigation
        service = navigation and navigation.getCurrentService()
        info = service and service.info()
        if info:
            try:
                from enigma import iServiceInformation
                def info_string(attr):
                    try:
                        return info.getInfoString(attr) or ""
                    except Exception:
                        return ""
                data["provider"] = info_string(iServiceInformation.sProvider)
                data["reference"] = info_string(iServiceInformation.sServiceref)
                for key, attr in (("video", "sVideoPID"), ("audio", "sAudioPID"),
                                  ("pcr", "sPCRPID"), ("pmt", "sPMTPID"),
                                  ("txt", "sTXTPID"), ("tsid", "sTSID"),
                                  ("onid", "sONID"), ("sid", "sSID")):
                    value_attr = getattr(iServiceInformation, attr, None)
                    if value_attr is not None:
                        try:
                            value = info.getInfo(value_attr)
                            if value is not None and value >= 0:
                                data["pids"][key] = value
                        except Exception:
                            pass
                ca_attr = getattr(iServiceInformation, "sCAIDs", None)
                if ca_attr is not None:
                    try:
                        caids = info.getInfoObject(ca_attr) or []
                        data["caids"] = [int(x) for x in caids if isinstance(x, int)]
                    except Exception:
                        pass
            except Exception:
                pass
        frontend = service and service.frontendInfo()
        if frontend:
            try:
                data["frontend"] = frontend.getAll(True) or {}
            except Exception:
                try:
                    data["frontend"] = frontend.getAll(False) or {}
                except Exception:
                    pass
    except Exception:
        pass
    return data


def channel_technical_summary():
    data = current_service_technical_information()
    rows = []
    if data["provider"]:
        rows.append(_("Provider: %s") % data["provider"])
    if data["reference"]:
        rows.append(_("Service reference: %s") % data["reference"])
    fe = data["frontend"]
    labels = (("tuner_type", _("System")), ("tuner_number", _("Tuner")),
              ("orbital_position", _("Orbital position")), ("frequency", _("Frequency")),
              ("polarization_abbreviation", _("Polarization")), ("symbol_rate", _("Symbol rate")),
              ("fec_inner", _("FEC")), ("modulation", _("Modulation")),
              ("system", _("Delivery system")), ("inversion", _("Inversion")),
              ("rolloff", _("Roll-off")), ("pilot", _("Pilot")),
              ("snr", _("SNR")), ("snr_db", _("SNR dB")), ("agc", _("AGC")), ("ber", _("BER")))
    for key, label in labels:
        value = fe.get(key)
        if value in (None, ""):
            continue
        if key == "orbital_position":
            value = _format_orbital_position(value)
        elif key == "frequency":
            value = _format_frontend_frequency(value)
        elif key == "symbol_rate":
            value = _format_symbol_rate(value)
        rows.append("%s: %s" % (label, value))
    if data["pids"]:
        rows += ["", _("Service IDs / PIDs")]
        for key in ("video", "audio", "pcr", "pmt", "txt", "tsid", "onid", "sid"):
            if key in data["pids"]:
                rows.append("%s: %s (0x%X)" % (key.upper(), data["pids"][key], data["pids"][key]))
    if data["caids"]:
        rows += ["", _("CAIDs: %s") % ", ".join("%04X" % value for value in data["caids"])]
    return "\n".join(rows) if rows else _("Current service technical data not exposed.")

def original_channel_overview_information():
    """GSU-style channel overview using only capabilities exposed by Enigma2/runtime."""
    rows = [_("GSU Channel Information"), "=" * 54, ""]
    name = _current_service_name()
    rows.append(_("Service: %s") % (name or _("not exposed")))
    rows += ["", "[ %s ]" % _("Tuner / frontend"), tuner_information()]
    active = _active_cam()
    rows += ["", "[ %s ]" % _("ECM / CAM")]
    if active:
        rows.append(active_cam_summary())
        if active.get("family") == "oscam":
            live, reason = oscam_live_rows()
            if live:
                values = _oscam_table_values(live[0])
                rows.extend([
                    _("Reader / User: %s") % (values["name"] or "N/A"),
                    _("Protocol: %s") % (values["protocol"] or "N/A"),
                    _("Service: %s") % (values["service"] or "N/A"),
                    _("Channel: %s") % (values["channel"] or name or "N/A"),
                    _("ECM: %s") % (values["ecm"] or "N/A"),
                    _("Status: %s") % (values["status"] or "N/A"),
                ])
            else:
                rows.append(reason or _("No active client/reader rows."))
    else:
        rows.append(_("No supported active CAM detected."))
    return "\n".join(rows)


def diagnostic_summary():
    oscam = bool(_find_processes("oscam"))
    network_mounts = 0
    for line in _read_lines("/proc/mounts"):
        fields = line.split()
        if len(fields) >= 3 and fields[2].lower() in ("nfs", "nfs4", "cifs", "smbfs"):
            network_mounts += 1
    mem = {}
    for line in _read_lines("/proc/meminfo"):
        if ":" in line:
            key, value = line.split(":", 1)
            mem[key] = value.strip()
    return "\n".join((
        "GSU diagnostic summary", "",
        "Receiver: %s" % _read_text("/proc/stb/info/model", platform.machine()),
        "Python: %s" % platform.python_version(),
        "Kernel: %s" % platform.release(),
        "Uptime: %s" % _uptime(),
        "Gateway: %s" % _default_gateway(),
        "OSCam: %s" % ("RUNNING" if oscam else "not detected"),
        "Network mounts: %d" % network_mounts,
        "Memory available: %s" % mem.get("MemAvailable", "N/A"),
    ))



def _version_key(value):
    """Compare Warder versions such as 13.25-w6 without float conversion."""
    text = (value or "").strip().lower().lstrip("v")
    parts = []
    for chunk in text.replace("-", ".").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _latest_release():
    """Read the public GitHub release manifest. No GitHub credentials are used."""
    req = urllib.request.Request(
        UPDATE_API,
        headers={"User-Agent": "Glass-System-Utility-Warder-Evolution/%s" % VERSION,
                 "Accept": "application/vnd.github+json"})
    try:
        response = urllib.request.urlopen(req, timeout=6)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    with response:
        data = json.loads(response.read().decode("utf-8", "replace"))
    tag = (data.get("tag_name") or "").strip()
    version = tag[1:] if tag.lower().startswith("v") else tag
    if not version or not all(char.isalnum() or char in ".-_" for char in version):
        return None
    name = "enigma2-plugin-glasssysutil_%s_all.ipk" % version
    ipk = next((asset for asset in (data.get("assets") or [])
                if asset.get("name") == name), None)
    if not ipk:
        return None
    url = ipk.get("browser_download_url") or ""
    parsed = urlsplit(url)
    expected_path = ("/Evolution-by-Warder/Glass-System-Utility-Warder-Evolution/"
                     "releases/download/%s/%s" % (tag, name))
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or
            parsed.username or parsed.password or parsed.port or parsed.path != expected_path):
        return None
    try:
        size = int(ipk.get("size") or 0)
    except (TypeError, ValueError):
        return None
    if size < 256:
        return None
    return {"version": version, "tag": tag, "url": url, "name": name, "size": size}


def _download_update(release):
    """Download an official release asset to a unique temporary file."""
    url = release.get("url") or ""
    name = release.get("name") or ""
    if name != "enigma2-plugin-glasssysutil_%s_all.ipk" % release.get("version"):
        raise ValueError("Release asset name does not match its version")
    parsed = urlsplit(url)
    expected_path = ("/Evolution-by-Warder/Glass-System-Utility-Warder-Evolution/"
                     "releases/download/%s/%s" % (release.get("tag"), name))
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or
            parsed.username or parsed.password or parsed.port or parsed.path != expected_path):
        raise ValueError("Release asset origin is invalid")

    fd, target = tempfile.mkstemp(prefix="gsu-update-", suffix=".ipk", dir="/tmp")
    os.close(fd)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Glass-System-Utility-Warder-Evolution/%s" % VERSION})
        with urllib.request.urlopen(req, timeout=20) as response, open(target, "wb") as handle:
            final = urlsplit(response.geturl())
            allowed_hosts = ("github.com", "objects.githubusercontent.com",
                             "release-assets.githubusercontent.com")
            content_type = (response.headers.get("Content-Type") or "").lower()
            if final.scheme != "https" or final.hostname not in allowed_hosts:
                raise ValueError("Unexpected GitHub download redirect host")
            if "text/html" in content_type:
                raise ValueError("GitHub returned an HTML page")
            received = 0
            expected_size = int(release["size"])
            while True:
                block = response.read(65536)
                if not block:
                    break
                received += len(block)
                if received > expected_size:
                    raise ValueError("Downloaded file exceeds GitHub metadata size")
                handle.write(block)
        if received != int(release["size"]):
            raise ValueError("Downloaded file size does not match GitHub metadata")
        with open(target, "rb") as handle:
            if handle.read(8) != b"!<arch>\n":
                raise ValueError("Downloaded file is not a valid IPK archive")
        return target
    except Exception:
        try:
            os.unlink(target)
        except Exception:
            pass
        raise


def _install_release(release):
    """Verify the IPK metadata before asking opkg to install it."""
    path = _download_update(release)
    try:
        rc_info, package_info = _run_status(["opkg", "info", path], 15)
        if rc_info != 0:
            raise ValueError("opkg could not parse the downloaded IPK")
        package_name = ""
        package_version = ""
        for line in package_info.splitlines():
            if line.startswith("Package:"):
                package_name = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                package_version = line.split(":", 1)[1].strip()
        expected_version = (release.get("version") or "").lower()
        actual_version = package_version[1:] if package_version.lower().startswith("v") else package_version
        if package_name != "enigma2-plugin-glasssysutil" or actual_version.lower() != expected_version:
            raise ValueError("IPK package identity or version does not match the GitHub release")
        rc, result = _run_status(["opkg", "install", path], 60)
        if rc != 0:
            raise RuntimeError("opkg install returned %d: %s" % (rc, result[-1200:]))
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


class GSUUpdater(object):
    def __init__(self, session):
        self.session = session
        self.release = None
        self.silent = True
        self.result = None
        self.worker = None
        self.timer = None
        self.progress = None
        self._timer_callback = self._poll

    def _start_timer(self):
        if eTimer is None:
            return False
        try:
            self.timer = eTimer()
            if hasattr(self.timer, "callback"):
                self.timer.callback.append(self._timer_callback)
            else:
                self.timer.timeout.get().append(self._timer_callback)
            self.timer.start(250, True)
            return True
        except Exception:
            self.timer = None
            return False

    def _poll(self):
        if self.result is None:
            self.timer.start(250, True)
            return
        try:
            self.timer.stop()
        except Exception:
            pass
        kind, value = self.result
        if kind == "check":
            self._finish_check(value)
        elif kind == "check-error":
            self._finish_check_error(value)
        else:
            self._finish_install(kind == "installed", value)

    def check(self, silent=True):
        self.silent = silent
        if eTimer is None:
            if not silent:
                self.session.open(MessageBox, _("Update check is unavailable on this Enigma2 image."),
                                  MessageBox.TYPE_INFO, timeout=5)
            return
        self.result = None
        if not self._start_timer():
            return
        try:
            self.worker = threading.Thread(target=self._check_worker, daemon=True)
            self.worker.start()
        except Exception as exc:
            self.result = ("check-error", str(exc))

    def _check_worker(self):
        try:
            self.result = ("check", _latest_release())
        except Exception as exc:
            self.result = ("check-error", str(exc))

    def _finish_check(self, result):
        release = result
        if not release or _version_key(release["version"]) <= _version_key(VERSION):
            if not self.silent:
                self.session.open(MessageBox,
                                  _("Glass System Utility %s is up to date.") % VERSION,
                                  MessageBox.TYPE_INFO, timeout=5)
            return
        self.release = release
        self.session.openWithCallback(
            self._answer, MessageBox,
            "Glass System Utility %s is available.\nInstalled: %s\n\nInstall the update now?"
            % (release["version"], VERSION), MessageBox.TYPE_YESNO)

    def _finish_check_error(self, detail):
        if not self.silent:
            self.session.open(MessageBox, _("Unable to check for updates.\n\n%s") % detail,
                              MessageBox.TYPE_INFO, timeout=8)

    def _answer(self, answer):
        if not answer or not self.release:
            return
        if eTimer is None or not self._start_timer():
            self.session.open(MessageBox, _("Update installation is unavailable on this Enigma2 image."),
                              MessageBox.TYPE_ERROR)
            return
        self.result = None
        self.progress = self.session.open(MessageBox, _("Downloading, verifying and installing the update..."),
                                          MessageBox.TYPE_INFO)
        try:
            self.worker = threading.Thread(target=self._install_worker, daemon=True)
            self.worker.start()
        except Exception as exc:
            self.result = ("install-error", str(exc))

    def _install_worker(self):
        try:
            _install_release(self.release)
            self.result = ("installed", "")
        except Exception as exc:
            self.result = ("install-error", str(exc))

    def _finish_install(self, success, detail):
        # Do not close the progress dialog and immediately open another modal.
        # OpenATV enforces modal ownership and can crash Enigma2 when a
        # background updater swaps MessageBoxes in this state.  Reuse the
        # already-open progress MessageBox for the final status instead.
        progress = self.progress
        self.progress = None
        if progress is None:
            return
        if not success:
            self._set_progress_text(progress, _("Update installation failed.\n\n%s") % detail)
            return

        self._set_progress_text(
            progress,
            "Update installed successfully.\nEnigma2 GUI will restart in 3 seconds.")
        self._schedule_gui_restart()

    def _set_progress_text(self, progress, message):
        try:
            progress["text"].setText(message)
            return
        except Exception:
            pass
        try:
            progress.setTitle(_("Glass System Utility"))
        except Exception:
            pass

    def _schedule_gui_restart(self):
        if eTimer is None:
            self._restart_after_update()
            return
        try:
            self.timer = eTimer()
            callback = self._restart_after_update
            self._restart_callback = callback
            if hasattr(self.timer, "callback"):
                self.timer.callback.append(callback)
            else:
                self.timer.timeout.get().append(callback)
            self.timer.start(3000, True)
        except Exception:
            self._restart_after_update()

    def _restart_after_update(self, *args):
        try:
            from Screens.Standby import TryQuitMainloop
            # Do not open TryQuitMainloop as another modal.  Its constructor
            # performs the quit request, so instantiate it directly.
            TryQuitMainloop(self.session, 3)
        except Exception:
            try:
                from enigma import quitMainloop
                quitMainloop(3)
            except Exception:
                pass



class GSUInfo(Screen):
    skin = """
    <screen name="GSUInfo" position="center,center" size="1160,680" title="Glass System Utility">
        <widget name="text" position="30,30" size="1100,620" font="Regular;25" scrollbarMode="showOnDemand" />
    </screen>
    """
    def __init__(self, session, title, text):
        Screen.__init__(self, session)
        self.setTitle(title)
        self["text"] = ScrollLabel(text) if ScrollLabel is not None else Label(text)
        actions = {"ok": self.close, "cancel": self.close}
        if ScrollLabel is not None:
            actions.update({
                "up": self["text"].pageUp, "down": self["text"].pageDown,
                "left": self["text"].pageUp, "right": self["text"].pageDown,
            })
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], actions, -1)



class GSUSystemDashboard(Screen):
    """Dense original-style system dashboard; all probes remain read-only."""
    skin = """
    <screen name="GlassSysInfo" position="0,0" size="1920,1080" title="GlassSysInfo" backgroundColor="#31000000" flags="wfNoBorder">
        <eLabel position="75,45" size="760,40" text="Memory / Storage / Temperature" font="priveG;28" foregroundColor="#666666" transparent="1"/>
        <widget name="resources" position="75,100" size="760,430" font="priveG;25" transparent="1"/>
        <eLabel position="75,555" size="760,40" text="System / Hardware" font="priveG;28" foregroundColor="#666666" transparent="1"/>
        <widget name="system" position="75,610" size="760,315" font="priveG;23" transparent="1"/>
        <eLabel position="925,45" size="900,40" text="Process Info" font="priveG;28" foregroundColor="#666666" transparent="1"/>
        <widget name="services" position="925,100" size="900,350" font="priveG;23" transparent="1"/>
        <eLabel position="925,475" size="900,40" text="Dmesg / Health Info" font="priveG;28" foregroundColor="#666666" transparent="1"/>
        <widget name="health" position="925,530" size="900,395" font="priveG;22" transparent="1"/>
        <eLabel position="75,945" size="150,35" text="Protocols:" font="priveG;25" foregroundColor="#666666" transparent="1"/>
        <widget name="protocols" position="230,945" size="1150,40" font="priveG;24" foregroundColor="#33cc33" transparent="1"/>
        <widget name="key_red" position="75,1010" size="300,45" font="priveG;30" foregroundColor="red" halign="center" transparent="1"/>
        <widget name="key_yellow" position="810,1010" size="300,45" font="priveG;30" foregroundColor="yellow" halign="center" transparent="1"/>
        <widget name="key_blue" position="1545,1010" size="300,45" font="priveG;30" foregroundColor="blue" halign="center" transparent="1"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        for key in ("system", "resources", "protocols", "services", "health"):
            self[key] = Label("")
        self["key_red"] = Label(_("Close"))
        self["key_yellow"] = Label(_("Refresh"))
        self["key_blue"] = Label(_("Tools"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, "red": self.close, "yellow": self.refresh,
            "blue": lambda: self.session.open(GSUWarderTools),
        }, -1)
        self.setTitle(_("System Information"))
        self.onShown.append(self.refresh)

    def refresh(self):
        self["system"].setText(system_information())
        self["resources"].setText(original_resource_dashboard_information())
        self["protocols"].setText(original_protocol_indicators())
        self["services"].setText(service_dashboard_information())
        self["health"].setText(storage_health_information() + "\n\n" + network_mount_doctor_information())


class GSUChannelDashboard(Screen):
    """Original-style current-channel dashboard using live Enigma2 and CAM data."""
    skin = """
    <screen name="Channel Info Center" position="0,0" size="1920,1080" title="Channel Info Center" backgroundColor="#31000000" flags="wfNoBorder">
        <widget name="channel" position="0,30" size="1859,120" font="priveG;57" valign="center" halign="center" transparent="1"/>
        <widget name="provider" position="592,127" size="675,90" font="priveG;39" valign="center" halign="center" transparent="1"/>
        <eLabel text="ECM Info" font="priveG;39" position="165,120" size="300,120" halign="center" valign="center" foregroundColor="#ff9c00" transparent="1"/>
        <widget name="ecmlabels" font="priveG;25" position="135,247" size="150,345" foregroundColor="#666666" transparent="1"/>
        <widget name="ecmValues" font="priveG;25" position="277,247" size="292,345" transparent="1"/>
        <eLabel text="Bitrate" font="priveG;39" position="180,619" size="300,120" halign="center" valign="center" foregroundColor="#ff9c00" transparent="1"/>
        <widget name="bit_labels" font="priveG;25" position="132,747" size="150,150" foregroundColor="#666666" transparent="1"/>
        <widget name="bit_min" font="priveG;25" position="244,747" size="135,150" transparent="1"/>
        <widget name="bit_max" font="priveG;25" position="331,747" size="135,150" transparent="1"/>
        <widget name="bit_avg" font="priveG;25" position="418,747" size="135,150" transparent="1"/>
        <widget name="bit_act" font="priveG;25" position="505,747" size="135,150" transparent="1"/>
        <widget name="stream_btr" font="priveG;25" position="244,839" size="450,30" transparent="1"/>
        <eLabel text="Transporder" font="priveG;39" position="1297,120" size="450,120" halign="center" valign="center" foregroundColor="#ff9c00" transparent="1"/>
        <widget name="tp_lab_sat" font="priveG;25" position="1300,247" size="200,30" foregroundColor="#666666" transparent="1"/>
        <widget name="tp_sat" font="priveG;25" position="1485,247" size="335,60" transparent="1"/>
        <widget name="tp_lab_ref" font="priveG;25" position="1300,312" size="200,30" foregroundColor="#666666" transparent="1"/>
        <widget name="tp_ref" font="priveG;25" position="1485,312" size="335,60" transparent="1"/>
        <widget name="tp_lab" font="priveG;25" position="1300,377" size="200,600" foregroundColor="#666666" transparent="1"/>
        <widget name="tp_values" font="priveG;25" position="1485,377" size="335,600" transparent="1"/>
        <eLabel text="Signal" font="priveG;39" position="780,619" size="300,120" halign="center" valign="center" foregroundColor="#ff9c00" transparent="1"/>
        <widget name="signal" font="priveG;25" position="777,775" size="390,70" transparent="1"/>
        <widget name="ids" position="715,855" size="500,105" font="priveG;22" transparent="1"/>
        <widget name="ecm" position="0,0" size="1,1" font="priveG;1" transparent="1"/>
        <widget name="technical" position="0,0" size="1,1" font="priveG;1" transparent="1"/>
        <eLabel position="810,975" size="300,2" backgroundColor="red"/>
        <widget name="red" font="priveG;30" position="0,985" size="1920,40" halign="center" foregroundColor="red" transparent="1"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self["channel"] = Label("")
        self["ecm"] = Label("")
        self["ids"] = Label("")
        self["tuner"] = Label("")
        self["key_red"] = Label(_("Close"))
        self["key_green"] = Label(_("CAM/SRV Manager"))
        self["key_yellow"] = Label(_("Refresh"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, "red": self.close,
            "green": lambda: self.session.open(GSUCamSrvManager),
            "yellow": self.refresh,
        }, -1)
        self.setTitle(_("Channel Information"))
        self.onShown.append(self.refresh)

    def refresh(self):
        data = current_service_technical_information()
        self["channel"].setText(data.get("name") or _("Current service"))
        self["provider"].setText(data.get("provider") or "")
        labels = [_("CAM"), _("System"), _("CAID"), _("Provider"), _("PID"), _("Protocol"), _("Address"), _("ECM Time")]
        values = []
        active = detect_active_cam()
        values.append(active.get("name") or "N/A"); values.append(active.get("family") or "N/A")
        values.append(", ".join("%04X" % x for x in data.get("caids", [])) or "N/A"); values.append(data.get("provider") or "N/A")
        values.append(str(data.get("pids", {}).get("video", "N/A")))
        live, _reason = oscam_live_rows() if active.get("family") == "oscam" else ([], "")
        row = _oscam_table_values(live[0]) if live else {}
        values += [row.get("protocol") or "N/A", row.get("address") or "N/A", row.get("ecm") or "N/A"]
        self["ecmlabels"].setText("\n".join(labels)); self["ecmValues"].setText("\n".join(values))
        self["bit_labels"].setText(_("MIN\nMAX\nAVG\nACT")); self["bit_min"].setText("N/A"); self["bit_max"].setText("N/A"); self["bit_avg"].setText("N/A"); self["bit_act"].setText("N/A")
        self["stream_btr"].setText(_("Bitrate backend not exposed by image."))
        fe=data.get("frontend",{}); self["tp_lab_sat"].setText(_("Satellite")); self["tp_sat"].setText(_format_orbital_position(fe.get("orbital_position")) if fe.get("orbital_position") not in (None,"") else "N/A")
        self["tp_lab_ref"].setText(_("Service ref.")); self["tp_ref"].setText(data.get("reference") or "N/A")
        keys=(("tuner_type",_("System")),("frequency",_("Frequency")),("polarization_abbreviation",_("Polarization")),("symbol_rate",_("Symbol rate")),("fec_inner",_("FEC")),("modulation",_("Modulation")))
        self["tp_lab"].setText("\n".join(label for key,label in keys)); self["tp_values"].setText("\n".join(str(fe.get(key) if fe.get(key) not in (None,"") else "N/A") for key,label in keys))
        self["signal"].setText("SNR: %s    AGC: %s    BER: %s" % (fe.get("snr","N/A"),fe.get("agc","N/A"),fe.get("ber","N/A")))
        self["ids"].setText(channel_technical_summary())
        self["ecm"].setText(ecm_information()); self["technical"].setText(channel_technical_summary())


class GSUECMInformation(Screen):
    """Original-character ECM center composed from live Enigma2/CAM data only."""
    skin = """
    <screen name="GSUECMInformation" position="center,center" size="930,790" title="ECM Information" backgroundColor="#31000000">
        <widget name="service" position="30,20" size="870,45" font="Regular;29" foregroundColor="#e6d500" halign="center" transparent="1"/>
        <eLabel position="0,80" size="930,2" backgroundColor="#888888"/>
        <widget name="service_context" position="35,100" size="410,210" font="Regular;22" transparent="1"/>
        <widget name="ecm_context" position="485,100" size="410,430" font="Regular;22" transparent="1"/>
        <eLabel position="465,100" size="2,430" backgroundColor="#888888"/>
        <widget name="ca_context" position="35,330" size="410,200" font="Regular;22" transparent="1"/>
        <eLabel position="0,550" size="930,2" backgroundColor="#888888"/>
        <widget name="info" position="35,570" size="860,105" font="Regular;20" foregroundColor="#888888" halign="center" valign="center" transparent="1"/>
        <eLabel position="0,705" size="310,2" backgroundColor="red"/>
        <eLabel position="310,705" size="310,2" backgroundColor="yellow"/>
        <eLabel position="620,705" size="310,2" backgroundColor="blue"/>
        <widget name="key_red" position="0,725" size="310,40" font="Regular;25" foregroundColor="red" halign="center" transparent="1"/>
        <widget name="key_yellow" position="310,725" size="310,40" font="Regular;25" foregroundColor="yellow" halign="center" transparent="1"/>
        <widget name="key_blue" position="620,725" size="310,40" font="Regular;25" foregroundColor="blue" halign="center" transparent="1"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["service"] = Label("")
        self["service_context"] = Label("")
        self["ca_context"] = Label("")
        self["ecm_context"] = Label("")
        self["info"] = Label(_("Live ECM information uses receiver-exposed service and CAM data; unavailable values are never invented."))
        self["key_red"] = Label(_("Exit"))
        self["key_yellow"] = Label(_("Refresh"))
        self["key_blue"] = Label(_("CAM/SRV"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, "red": self.close, "yellow": self.refresh,
            "blue": self.open_cam_manager,
        }, -1)
        self.setTitle(_("ECM Information"))
        self.onShown.append(self.refresh)

    def open_cam_manager(self):
        self.session.open(GSUCamSrvManager)

    def refresh(self):
        service = current_service_technical_information()
        name = service.get("name") or _current_service_name() or _("Current service not exposed")
        self["service"].setText(name)

        service_rows = [
            _("Provider: %s") % (service.get("provider") or _("not exposed")),
        ]
        frontend = service.get("frontend") or {}
        orbital = frontend.get("orbital_position")
        if orbital not in (None, ""):
            service_rows.append(_("Orbital position: %s") % _format_orbital_position(orbital))
        reference = service.get("reference")
        if reference:
            service_rows.append(_("Service reference: %s") % reference)
        self["service_context"].setText("\n".join(service_rows))

        caids = service.get("caids") or []
        ca_rows = [_("Available CAIDs")]
        ca_rows.extend("%04X" % value for value in caids)
        if not caids:
            ca_rows.append(_("not exposed"))
        self["ca_context"].setText("\n".join(ca_rows))

        active = _active_cam()
        rows = [active_cam_summary() if active else _("No supported active CAM detected.")]
        if active and active.get("family") == "oscam":
            live, reason = oscam_live_rows()
            if live:
                values = _oscam_table_values(live[0])
                rows += [
                    "",
                    _("Reader / User: %s") % (values["name"] or "N/A"),
                    _("Address: %s") % (values["address"] or "N/A"),
                    _("Port: %s") % (values["port"] or "N/A"),
                    _("Protocol: %s") % (values["protocol"] or "N/A"),
                    _("Service: %s") % (values["service"] or "N/A"),
                    _("Channel: %s") % (values["channel"] or name or "N/A"),
                    _("ECM: %s") % (values["ecm"] or "N/A"),
                    _("Idle: %s") % (values["idle"] or "N/A"),
                    _("Status: %s") % (values["status"] or "N/A"),
                ]
            elif reason:
                rows += ["", reason]
        self["ecm_context"].setText("\n".join(rows))


class GSUCamSrvManager(Screen):
    """Original CAM/SRV landing screen wrapping the proven OSCam monitor backend."""
    skin = """
    <screen name="Glass Cams Manager" position="center,center" size="1530,895" title="UCM" backgroundColor="#31000000">
        <eLabel position="30,20" size="700,40" text="CAM-y / SRV-e" font="Regular;28" foregroundColor="#666666" transparent="1"/>
        <widget name="cam" position="30,75" size="700,300" font="Regular;24" transparent="1"/>
        <eLabel position="800,20" size="700,40" text="Aktívny CAM / Aktívny SRV" font="Regular;28" foregroundColor="#666666" transparent="1"/>
        <widget name="service" position="800,75" size="700,300" font="Regular;24" transparent="1"/>
        <eLabel position="30,405" size="1470,2" backgroundColor="#888888"/>
        <eLabel position="30,430" size="1470,40" text="ECM / CAID / Process status" font="Regular;27" foregroundColor="#666666" transparent="1"/>
        <widget name="status" position="30,485" size="1470,275" font="Regular;23" transparent="1"/>
        <eLabel position="0,790" size="382,2" backgroundColor="red"/>
        <eLabel position="382,790" size="383,2" backgroundColor="green"/>
        <eLabel position="765,790" size="382,2" backgroundColor="yellow"/>
        <eLabel position="1147,790" size="383,2" backgroundColor="blue"/>
        <widget name="key_red" position="0,810" size="382,45" font="Regular;27" foregroundColor="red" halign="center" transparent="1"/>
        <widget name="key_green" position="382,810" size="383,45" font="Regular;27" foregroundColor="green" halign="center" transparent="1"/>
        <widget name="key_yellow" position="765,810" size="382,45" font="Regular;27" foregroundColor="yellow" halign="center" transparent="1"/>
        <widget name="key_blue" position="1147,810" size="383,45" font="Regular;27" foregroundColor="blue" halign="center" transparent="1"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self["cam"] = Label("")
        self["service"] = Label("")
        self["status"] = Label("")
        self["key_red"] = Label(_("Close"))
        self["key_green"] = Label(_("OSCam monitor"))
        self["key_yellow"] = Label(_("Refresh"))
        self["key_blue"] = Label(_("ECM details"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, "red": self.close,
            "green": lambda: self.session.open(GSUActiveCAM),
            "yellow": self.refresh,
            "blue": lambda: self.session.open(GSUECMInformation),
        }, -1)
        self.setTitle(_("CAM/SRV Manager"))
        self.onShown.append(self.refresh)

    def refresh(self):
        self["cam"].setText(cam_srv_context_information())
        technical = current_service_technical_information()
        fe = technical.get("frontend") or {}
        rows = [_("Channel: %s") % (technical.get("name") or _("not exposed")),
                _("Provider: %s") % (technical.get("provider") or _("not exposed"))]
        if fe.get("orbital_position") not in (None, ""):
            rows.append(_("Orbital position: %s") % _format_orbital_position(fe.get("orbital_position")))
        caids = technical.get("caids") or []
        rows.append(_("Available CAIDs: %s") % (
            ", ".join("%04X" % value for value in caids) if caids else _("not exposed")))
        self["service"].setText("\n".join(rows))
        command, detail = _active_cam_restart_command()
        active = _active_cam()
        status_rows = [active_cam_summary() if active else _("No supported active CAM detected.")]
        if active and active.get("family") == "oscam":
            live, reason = oscam_live_rows()
            if live:
                values = _oscam_table_values(live[0])
                status_rows += [
                    "",
                    _("Reader / User: %s") % (values["name"] or "N/A"),
                    _("Address: %s") % (values["address"] or "N/A"),
                    _("Port: %s") % (values["port"] or "N/A"),
                    _("Protocol: %s") % (values["protocol"] or "N/A"),
                    _("Service: %s") % (values["service"] or "N/A"),
                    _("Channel: %s") % (values["channel"] or technical.get("name") or "N/A"),
                    _("ECM: %s") % (values["ecm"] or "N/A"),
                    _("Idle: %s") % (values["idle"] or "N/A"),
                    _("Status: %s") % (values["status"] or "N/A"),
                ]
            elif reason:
                status_rows += ["", reason]
        status_rows += [
            "",
            _("CAM restart: %s") % (_("available") if command else _("unavailable")),
            detail or _("No image-supported restart command exposed."),
            _("Stop / activate / download / delete actions remain disabled until receiver validation."),
        ]
        self["status"].setText("\n".join(status_rows))


class GSUActiveCAM(Screen):
    """Visual OSCam/CAM monitor with a compact live table and safe actions."""
    skin = """
    <screen name="GSUActiveCAM" position="center,center" size="1500,820" title="OSCam Information">
        <eLabel position="25,12" size="710,32" text="CAM / SRV status" font="Regular;21" foregroundColor="#3399ff" />
        <widget name="summary" position="25,48" size="710,95" font="Regular;21" />
        <widget name="service_context" position="760,20" size="715,52" font="Regular;21" foregroundColor="#e6d500" />
        <widget name="ecm_context" position="760,73" size="715,52" font="Regular;20" foregroundColor="#33cc33" />
        <widget name="live_status" position="25,148" size="1450,32" font="Regular;20" foregroundColor="#33cc33" />
        <eLabel position="45,190" size="165,34" font="Regular;18" foregroundColor="#e6d500" text="Reader / User" />
        <eLabel position="225,190" size="190,34" font="Regular;18" foregroundColor="#e6d500" text="Address" />
        <eLabel position="430,190" size="75,34" font="Regular;18" foregroundColor="#e6d500" text="Port" />
        <eLabel position="520,190" size="130,34" font="Regular;18" foregroundColor="#e6d500" text="Protocol" />
        <eLabel position="665,190" size="225,34" font="Regular;18" foregroundColor="#e6d500" text="srvid:caid@provid" />
        <eLabel position="905,190" size="225,34" font="Regular;18" foregroundColor="#e6d500" text="Channel" />
        <eLabel position="1145,190" size="95,34" font="Regular;18" foregroundColor="#e6d500" text="ECM" />
        <eLabel position="1255,190" size="80,34" font="Regular;18" foregroundColor="#e6d500" text="Idle" />
        <eLabel position="1350,190" size="150,34" font="Regular;18" foregroundColor="#e6d500" text="Status" />
        <eLabel position="215,188" size="1,505" backgroundColor="#555555" />
        <eLabel position="420,188" size="1,505" backgroundColor="#555555" />
        <eLabel position="510,188" size="1,505" backgroundColor="#555555" />
        <eLabel position="655,188" size="1,505" backgroundColor="#555555" />
        <eLabel position="895,188" size="1,505" backgroundColor="#555555" />
        <eLabel position="1135,188" size="1,505" backgroundColor="#555555" />
        <eLabel position="1245,188" size="1,505" backgroundColor="#555555" />
        <eLabel position="1340,188" size="1,505" backgroundColor="#555555" />
        <widget source="table" render="Listbox" position="25,227" size="1450,465" scrollbarMode="showOnDemand">
            <convert type="TemplatedMultiContent">
                {"template": [MultiContentEntryText(pos=(20,0),size=(165,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=1),
                              MultiContentEntryText(pos=(200,0),size=(190,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=2),
                              MultiContentEntryText(pos=(405,0),size=(75,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=3),
                              MultiContentEntryText(pos=(495,0),size=(130,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=4),
                              MultiContentEntryText(pos=(640,0),size=(225,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=5),
                              MultiContentEntryText(pos=(880,0),size=(225,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=6),
                              MultiContentEntryText(pos=(1120,0),size=(95,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=7),
                              MultiContentEntryText(pos=(1230,0),size=(80,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=8),
                              MultiContentEntryText(pos=(1325,0),size=(150,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=9)],
                 "fonts":[gFont("Regular",18)],"itemHeight":34}
            </convert>
        </widget>
        <widget name="key_red" position="35,750" size="230,45" font="Regular;24" foregroundColor="#ff3333" />
        <widget name="key_green" position="380,750" size="250,45" font="Regular;24" foregroundColor="#33cc33" />
        <widget name="key_yellow" position="760,750" size="220,45" font="Regular;24" foregroundColor="#e6d500" />
        <widget name="key_blue" position="1180,750" size="220,45" font="Regular;24" foregroundColor="#3399ff" />
    </screen>
    """
    TABLE_HEADER = "  Reader/User     Address          Port   Protocol   srvid:caid@provid     Channel                  ECM       Idle      Status"

    def __init__(self, session):
        Screen.__init__(self, session)
        self["summary"] = Label(cam_srv_context_information())
        self["live_status"] = Label("")
        self["service_context"] = Label("")
        self["ecm_context"] = Label("")
        self._table_uses_list_source = List is not None
        if self._table_uses_list_source:
            self["table"] = List([])
        else:
            self["table"] = MenuList([])
        self.setTitle(_("OSCam Information"))
        self["key_red"] = Label(_("Close"))
        command, detail = _active_cam_restart_command()
        self.restart_command = command
        self.restart_detail = detail
        self["key_green"] = Label(_("Restart CAM") if command else _("Restart unavailable"))
        self["key_yellow"] = Label(_("Refresh"))
        self["key_blue"] = Label(_("Details"))
        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions"], {
                "cancel": self.close,
                "ok": self.show_selected_row,
                "red": self.close,
                "green": self.restart_cam,
                "yellow": self._refresh,
                "blue": self.show_details,
                "up": self["table"].up,
                "down": self["table"].down,
                "left": self["table"].pageUp,
                "right": self["table"].pageDown,
            }, -1)
        self._live_rows = []
        self._refresh_in_progress = False
        self._live_fetch_running = False
        self._restart_in_progress = False
        self._closing_live_monitor = False
        # w11 fixed-column monitor contract: source, package and receiver UI move together.
        # Candidate is gated by CI before immutable release publication.
        # Final w11 release candidate validation marker.
        # Receiver polish: narrower identity column, wider status, DVBAPI channel fallback.
        # 13.31-w12 release validation.
        # post-w12 operational batch validation
        # 13.32-w13 final candidate
        self._refresh()
        self._start_auto_refresh()

    def _set_live_rows(self, rows, reason=""):
        self._live_rows = list(rows or [])
        selected = 0
        try:
            selected = self["table"].getSelectionIndex()
        except Exception:
            pass
        items = ([_oscam_list_tuple(row) for row in rows] if self._table_uses_list_source
                 else [_oscam_table_line(row) for row in rows])
        self["table"].setList(items)
        if rows:
            try:
                self["table"].moveToIndex(min(selected, len(rows) - 1))
            except Exception:
                pass
            self["live_status"].setText(_("Live OSCam: %d active client/reader rows  |  OK = row details") % len(rows))
        else:
            self["live_status"].setText(_("Live OSCam: %s") % (reason or _("No active client/reader rows.")))

    def _refresh(self):
        if getattr(self, "_closing_live_monitor", False):
            return
        if getattr(self, "_refresh_in_progress", False):
            return
        self._refresh_in_progress = True
        try:
            try:
                self["summary"].setText(cam_srv_context_information())
                self["service_context"].setText(_("Channel: %s") % (_current_service_name() or _("not exposed")))
            except Exception:
                pass
            active = _active_cam()
            table_rows, reason = ([], "No supported active OSCam detected.")
            if active and active.get("family") == "oscam":
                table_rows, reason = oscam_live_rows()
            try:
                self._set_live_rows(table_rows, reason)
                if table_rows:
                    values = _oscam_table_values(table_rows[0])
                    self["ecm_context"].setText(_("ECM: %s   CA: %s   Status: %s") % (values["ecm"] or "N/A", values["service"] or "N/A", values["status"] or "N/A"))
                else:
                    self["ecm_context"].setText(_("ECM: no live data"))
            except Exception:
                pass
            command, detail = _active_cam_restart_command()
            self.restart_command = command
            self.restart_detail = detail
            try:
                self["key_green"].setText(_("Restart CAM") if command else _("Restart unavailable"))
            except Exception:
                pass
        finally:
            self._refresh_in_progress = False

    def _start_auto_refresh(self):
        if eTimer is None:
            return
        self._live_timer = eTimer()
        try:
            self._live_timer.callback.append(self._auto_refresh)
        except Exception:
            self._live_timer.timeout.connect(self._auto_refresh)
        self._live_timer.start(5000, False)

    def _auto_refresh(self):
        if getattr(self, "_closing_live_monitor", False):
            return
        if getattr(self, "_live_fetch_running", False):
            return
        self._live_fetch_running = True

        def worker():
            active = _active_cam()
            rows, reason = ([], "No supported active OSCam detected.")
            if active and active.get("family") == "oscam":
                rows, reason = oscam_live_rows()

            def finish():
                self._restart_in_progress = False
                if getattr(self, "_closing_live_monitor", False):
                    self._live_fetch_running = False
                    return
                try:
                    self._set_live_rows(rows, reason)
                    try:
                        self["summary"].setText(active_cam_summary())
                        self["service_context"].setText(_("Channel: %s") % (_current_service_name() or _("not exposed")))
                        if rows:
                            values = _oscam_table_values(rows[0])
                            self["ecm_context"].setText(_("ECM: %s   CA: %s   Status: %s") % (values["ecm"] or "N/A", values["service"] or "N/A", values["status"] or "N/A"))
                        else:
                            self["ecm_context"].setText(_("ECM: no live data"))
                    except Exception:
                        pass
                finally:
                    self._live_fetch_running = False
                    timer = getattr(self, "_live_finish_timer", None)
                    if timer is not None:
                        try:
                            timer.stop()
                        except Exception:
                            pass

            if eTimer is None:
                finish()
            else:
                timer = eTimer()
                self._live_finish_timer = timer
                try:
                    timer.callback.append(finish)
                except Exception:
                    timer.timeout.connect(finish)
                timer.start(1, True)

        try:
            threading.Thread(target=worker, name="GSU-OSCam-Live", daemon=True).start()
        except Exception:
            self._live_fetch_running = False

    def close(self, *args, **kwargs):
        self._closing_live_monitor = True
        self._live_fetch_running = True
        for timer_name in ("_live_timer", "_live_finish_timer", "_restart_finish_timer"):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                try:
                    timer.stop()
                except Exception:
                    pass
        return Screen.close(self, *args, **kwargs)

    def show_selected_row(self):
        try:
            current = self["table"].getCurrent()
        except Exception:
            current = None
        row = None
        if self._table_uses_list_source and current:
            if isinstance(current, dict):
                row = current
            elif isinstance(current, (tuple, list)) and current and isinstance(current[0], dict):
                row = current[0]
        if row is None:
            try:
                index = self["table"].getSelectionIndex()
                if 0 <= index < len(self._live_rows):
                    row = self._live_rows[index]
            except Exception:
                row = None
        if not isinstance(row, dict):
            return
        values = _oscam_table_values(row)
        lines = [
            "Reader / User: %s" % (values["name"] or "N/A"),
            "Address: %s" % (values["address"] or "N/A"),
            "Port: %s" % (values["port"] or "N/A"),
            "Protocol: %s" % (values["protocol"] or "N/A"),
            "Service: %s" % (values["service"] or "N/A"),
            "Channel: %s" % (values["channel"] or "N/A"),
            "ECM: %s" % (values["ecm"] or "N/A"),
            "Idle: %s" % (values["idle"] or "N/A"),
            "Status: %s" % (values["status"] or "N/A"),
        ]
        self.session.open(MessageBox, "\n".join(lines), MessageBox.TYPE_INFO)

    def show_details(self):
        active = _active_cam()
        if not active:
            self.session.open(MessageBox, _("No supported active CAM detected."), MessageBox.TYPE_INFO, timeout=6)
            return
        parts = [oscam_information() if active.get("family") == "oscam" else active_cam_information()]
        if active.get("family") == "oscam":
            parts.extend(["", oscam_runtime_information(), "", oscam_webif_information()])
        self.session.open(GSUInfo, _("OSCam Information"), "\n".join(parts))

    def restart_cam(self):
        if getattr(self, "_restart_in_progress", False):
            return
        if not self.restart_command:
            self.session.open(MessageBox, self.restart_detail, MessageBox.TYPE_INFO, timeout=8)
            return
        self.session.openWithCallback(
            self._restart_confirmed,
            MessageBox,
            "%s?\n\nThe currently active CAM will be briefly interrupted." % self.restart_detail,
            MessageBox.TYPE_YESNO)

    def _restart_confirmed(self, answer):
        if not answer:
            return
        if getattr(self, "_restart_in_progress", False):
            return
        self._restart_in_progress = True
        command = list(self.restart_command)
        before = _active_cam()
        before_pid = before["pid"] if before else ""

        def worker():
            rc, output = _run_status(command, 12)
            verified = None
            if rc == 0:
                for _attempt in range(8):
                    time.sleep(0.5)
                    verified = _active_cam()
                    if verified:
                        break

            def finish():
                if getattr(self, "_closing_live_monitor", False):
                    return
                self._refresh()
                if rc != 0:
                    detail = output[-800:] if output else "restart command returned status %s" % rc
                    self.session.open(MessageBox, _("Active CAM restart failed.\n\n%s") % detail,
                                      MessageBox.TYPE_ERROR, timeout=10)
                elif verified:
                    changed = " (new PID %s)" % verified["pid"] if verified["pid"] != before_pid else ""
                    self.session.open(MessageBox, _("Active CAM restart verified%s.") % changed,
                                      MessageBox.TYPE_INFO, timeout=6)
                else:
                    self.session.open(MessageBox,
                                      _(_("Restart command completed, but no active CAM was detected afterwards.")),
                                      MessageBox.TYPE_ERROR, timeout=10)
                timer = getattr(self, "_restart_finish_timer", None)
                if timer is not None:
                    try:
                        timer.stop()
                    except Exception:
                        pass

            if eTimer is None:
                finish()
            else:
                timer = eTimer()
                self._restart_finish_timer = timer
                try:
                    timer.callback.append(finish)
                except Exception:
                    timer.timeout.connect(finish)
                timer.start(1, True)

        try:
            threading.Thread(target=worker, name="GSU-CAM-Restart", daemon=True).start()
        except Exception:
            self._restart_in_progress = False
            self.session.open(MessageBox, _("Unable to start CAM restart worker."), MessageBox.TYPE_ERROR, timeout=8)

class SysUtilMngMain(Screen):
    """GSU 13.20 top-level presentation backed by the modern Warder runtime."""
    skin = """
    <screen name="GlassSysUtil" position="center,center" size="930,790" title="Glass System Utility" backgroundColor="#31000000">
        <widget name="list" position="30,0" size="412,600"  zPosition="2" scrollbarMode="showOnDemand" backgroundColor="#31000000" />\n        <ePixmap position="495,55" zPosition="1" size="340,480" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil/fhd/sys_util.png" transparent="1"  alphatest="off"/>
        <eLabel position="0,607" size="930,2" backgroundColor="#888888" zPosition="5" transparent="0" />
        <widget name="info" position="30,610" size="870,120" font="priveG;25" zPosition="4" valign="center" halign="center" foregroundColor="#666666" transparent="1" />
        <eLabel position="0,733" size="232,2" backgroundColor="red" zPosition="5" transparent="0" />
        <eLabel position="232,733" size="233,2" backgroundColor="green" zPosition="5" transparent="0" />
        <eLabel position="465,733" size="232,2" backgroundColor="yellow" zPosition="5" transparent="0" />
        <eLabel position="697,733" size="233,2" backgroundColor="blue" zPosition="5" transparent="0" />
        <widget name="red" position="0,743" size="232,37" font="priveG;30" valign="center" halign="center" foregroundColor="red" transparent="1"/>
        <widget name="green" position="232,743" size="233,37" font="priveG;30" valign="center" halign="center" foregroundColor="green" transparent="1"/>
        <widget name="yellow" position="465,743" size="232,37" font="priveG;30" valign="center" halign="center" foregroundColor="yellow" transparent="1"/>
        <widget name="blue" position="697,743" size="233,37" font="priveG;30" valign="center" halign="center" foregroundColor="blue" transparent="1"/>
    </screen>
    """
    MENU = [
        (_("System Information"), "originalsystem"),
        (_("Channel Information"), "originalchannel"),
        (_("CCcam Information"), "cccaminfo"),
        (_("OSCam Information"), "oscaminfo"),
        (_("Mbox Information"), "mboxinfo"),
        (_("IPK/DEB and user scripts"), "packagetools"),
        (_("ECM Information"), "ecminfo"),
        (_("CAM/SRV Manager"), "cammanager"),
        (_("OSD ECM Information"), "osdecm"),
        (_("Swap Manager"), "swapmanager"),
        (_("Channel settings"), "channelsettings"),
        (_("Device Manager"), "devicemanager"),
        (_("Automatic installations"), "autoinstall"),
        (_("Crond Manager"), "crond"),
        (_("Text editor"), "texteditor"),
        (_("Reset root user password"), "rootpassword"),
    ]
    HELP = {
        "originalsystem": _("Displays system, memory, storage, temperature, process and service information."),
        "originalchannel": _("Displays current channel, ECM, bitrate, signal and transponder information."),
        "cccaminfo": _("CCcam information is available only when a compatible CCcam runtime is detected."),
        "oscaminfo": _("Displays OSCam runtime, clients/readers and decoding information."),
        "mboxinfo": _("Mbox information is available only when a compatible Mbox runtime is detected."),
        "packagetools": _("User scripts and local IPK/DEB/TAR package tools."),
        "ecminfo": _("Displays current ECM and conditional-access information."),
        "cammanager": _("Manage and inspect the active CAM/SRV using image-supported mechanisms."),
        "osdecm": _("Displays live service, CAID, CAM and ECM context using the modern receiver backend."),
        "swapmanager": _("Displays active swap capacity, usage, priority and receiver memory information."),
        "channelsettings": _("Inspects Enigma2 service databases, tuning definitions and bouquet contents read-only."),
        "devicemanager": _("Displays mounted storage, block devices, model/vendor and removable-device information."),
        "autoinstall": _("Inspects local IPK/DEB/archive/script installation candidates without remote execution."),
        "crond": _("Displays cron daemon state, job files and a bounded schedule preview read-only."),
        "texteditor": _("Inspects common Enigma2/system text configuration candidates; arbitrary writes remain gated."),
        "rootpassword": _("Displays root account and password-tool capability; password mutation remains gated."),
    }

    def __init__(self, session):
        Screen.__init__(self, session)
        self["list"] = MenuList([item[0] for item in self.MENU])
        self["info"] = Label("")
        self["red"] = Label(_("Exit"))
        self["green"] = Label(_("OK"))
        self["yellow"] = Label(_("Refresh"))
        self["blue"] = Label(_("Help"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.ok, "cancel": self.close, "red": self.close, "green": self.ok,
            "yellow": self._refresh_context, "blue": self.open_help,
            "up": self._up, "down": self._down,
        }, -1)
        self.setTitle("GSU ver. %s" % VERSION)
        self.onShown.append(self._check_update_on_open)
        self.onShown.append(self._refresh_context)

    def _selected_action(self):
        try:
            return self.MENU[self["list"].getSelectedIndex()][1]
        except Exception:
            return ""

    def _refresh_context(self):
        self["info"].setText(self.HELP.get(self._selected_action(), ""))

    def _up(self):
        self["list"].up()
        self._refresh_context()

    def _down(self):
        self["list"].down()
        self._refresh_context()

    def _check_update_on_open(self):
        try:
            self.onShown.remove(self._check_update_on_open)
        except Exception:
            pass
        try:
            GSUUpdater(self.session).check(silent=True)
        except Exception:
            pass

    def _info(self, title, text):
        self.session.open(GSUInfo, title, text)

    def open_help(self):
        action = self._selected_action()
        title = self.MENU[self["list"].getSelectedIndex()][0] if action else _("Glass System Utility")
        self.session.open(GSUInfo, title, self.HELP.get(action, _("No additional information.")))

    def ok(self):
        action = self._selected_action()
        if action == "originalsystem":
            self.session.open(GSUSystemDashboard)
        elif action == "originalchannel":
            self.session.open(GSUChannelDashboard)
        elif action == "oscaminfo":
            self.session.open(GSUActiveCAM)
        elif action == "cammanager":
            self.session.open(GSUCamSrvManager)
        elif action == "ecminfo":
            self.session.open(GSUECMInformation)
        elif action == "devicemanager":
            self.session.open(GSUDeviceManager)
        elif action == "swapmanager":
            self.session.open(GSUSwapManager)
        elif action == "packagetools":
            self.session.open(GSUPackageCenter)
        elif action == "cccaminfo":
            self.session.open(GSULegacyCAMCenter, "cccam")
        elif action == "mboxinfo":
            self.session.open(GSULegacyCAMCenter, "mbox")
        elif action == "channelsettings":
            self.session.open(GSUChannelSettingsCenter)
        elif action == "crond":
            self.session.open(GSUCrondManager)
        elif action == "texteditor":
            self.session.open(GSUTextEditorCenter)
        elif action == "rootpassword":
            self.session.open(GSURootPasswordCenter)
        elif action == "osdecm":
            self.session.open(GSUOSDECMCenter)
        elif action == "autoinstall":
            self.session.open(GSUAutoInstallCenter)



class GSUOriginalStatusCenter(Screen):
    """Original GSU maintenance-center visual shell with modern safe providers."""
    skin = """
    <screen name="GlassOriginalMaintenanceCenter" position="center,center" size="930,790" title="GSU" backgroundColor="#31000000">
        <widget name="titleline" position="30,20" size="870,45" font="Regular;29" foregroundColor="#e6d500" halign="center" transparent="1"/>
        <eLabel position="0,80" size="930,2" backgroundColor="#888888"/>
        <widget name="body" position="35,100" size="860,485" font="Regular;23" transparent="1"/>
        <eLabel position="0,600" size="930,2" backgroundColor="#888888"/>
        <widget name="info" position="35,615" size="860,70" font="Regular;20" foregroundColor="#888888" halign="center" valign="center" transparent="1"/>
        <eLabel position="0,705" size="232,2" backgroundColor="red"/>
        <eLabel position="232,705" size="233,2" backgroundColor="green"/>
        <eLabel position="465,705" size="232,2" backgroundColor="yellow"/>
        <eLabel position="697,705" size="233,2" backgroundColor="blue"/>
        <widget name="red" position="0,725" size="232,40" font="Regular;25" foregroundColor="red" halign="center" transparent="1"/>
        <widget name="green" position="232,725" size="233,40" font="Regular;25" foregroundColor="green" halign="center" transparent="1"/>
        <widget name="yellow" position="465,725" size="232,40" font="Regular;25" foregroundColor="yellow" halign="center" transparent="1"/>
        <widget name="blue" position="697,725" size="233,40" font="Regular;25" foregroundColor="blue" halign="center" transparent="1"/>
    </screen>
    """
    def __init__(self, session, title, provider, help_text):
        Screen.__init__(self, session)
        self._provider = provider
        self["titleline"] = Label(title)
        self["body"] = Label("")
        self["info"] = Label(help_text)
        self["red"] = Label(_("Exit"))
        self["green"] = Label(_("OK"))
        self["yellow"] = Label(_("Refresh"))
        self["blue"] = Label(_("Help"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, "red": self.close,
            "green": self.refresh, "ok": self.refresh, "yellow": self.refresh,
            "blue": self.show_help,
        }, -1)
        self.setTitle(title)
        self.onShown.append(self.refresh)

    def refresh(self):
        try:
            self["body"].setText(self._provider())
        except Exception as error:
            self["body"].setText(_("Unable to read status: %s") % error)

    def show_help(self):
        self.session.open(GSUInfo, self.getTitle(), self["info"].getText())


class GSULegacyCAMCenter(GSUOriginalStatusCenter):
    def __init__(self, session, family):
        self._family = family
        title = "CCcam Information" if family == "cccam" else "Mbox Information"
        GSUOriginalStatusCenter.__init__(
            self, session, _(title), lambda: legacy_cam_information(self._family),
            _("Legacy CAM runtime and configuration location are inspected read-only; credentials are never displayed."))


class GSUSwapManager(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("Swap Manager"), swap_manager_information,
                                         _("Original swap controls are retained; state changes remain gated until receiver validation."))


class GSUDeviceManager(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("Device Manager"), device_manager_information,
                                         _("Device detection is live; destructive actions remain safety-gated."))


class GSUCrondManager(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("Crond Manager"), cron_manager_information,
                                         _("Cron state is live; editing remains gated until receiver validation."))


class GSUTextEditorCenter(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("Text editor"), text_editor_information,
                                         _("Original editor workflow is retained; arbitrary writes remain safety-gated."))


class GSUChannelSettingsCenter(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("Channel settings"), channel_settings_information,
                                         _("Channel capability is detected without modifying bouquets."))


class GSURootPasswordCenter(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("Reset root user password"), root_password_information,
                                         _("Password mutation remains disabled until a receiver-safe confirmation flow is validated."))


class GSUAutoInstallCenter(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("Automatic installations"), automatic_installation_information,
                                         _("Original automatic-installation workflow is retained without reviving unsafe remote installers."))


class GSUOSDECMCenter(GSUOriginalStatusCenter):
    def __init__(self, session):
        GSUOriginalStatusCenter.__init__(self, session, _("OSD ECM Information"), osd_ecm_information,
                                         _("OSD ECM uses the modern live service/CAM backend; display mutation remains gated."))


class GSUPackageCenter(Screen):
    """Original GSU IPK/DEB/user-script center; mutation stays capability-gated."""
    skin = """
    <screen name="GlassIpkScriptCenter" position="center,center" size="750,530" title="Ipk and Script Manager" backgroundColor="#31000000" >
        <widget name="list" position="30,30" size="690,294" scrollbarMode="showOnDemand" backgroundColor="#31000000" />
        <eLabel position="0,339" size="750,2" backgroundColor="#888888" zPosition="5" transparent="0" />
        <widget name="info" position="30,342" size="690,117" font="priveG;25" valign="center" halign="center" foregroundColor="#666666" transparent="1" />
        <eLabel position="0,470" size="375,2" backgroundColor="red" zPosition="5" transparent="0" />
        <eLabel position="375,470" size="375,2" backgroundColor="green" zPosition="5" transparent="0" />
        <widget name="red" font="priveG;30" position="0,480" size="375,40" zPosition="1" halign="center" valign="top" backgroundColor="#31000000" foregroundColor="red" transparent="1"/>
        <widget name="green" font="priveG;30" position="375,480" size="375,40" zPosition="1" halign="center" valign="top" backgroundColor="#31000000" foregroundColor="green" transparent="1"/>
    </screen>
    """
    MENU = [
        (_("User scripts"), _("Browse and run user scripts only after the execution path is receiver-validated.")),
        (_("Install IPK"), _("Local IPK installation is retained but remains gated until receiver validation.")),
        (_("Uninstall IPK"), _("Installed-package removal is retained but remains gated until receiver validation.")),
        (_("Install TAR"), _("Local TAR installation is retained but remains gated until receiver validation.")),
        (_("Install/Uninstall DEB"), _("DEB handling is enabled only on images exposing a compatible package manager.")),
    ]

    def __init__(self, session):
        Screen.__init__(self, session)
        self["list"] = MenuList([x[0] for x in self.MENU])
        self["info"] = Label("")
        self["red"] = Label(_("Exit"))
        self["green"] = Label(_("OK"))
        self["yellow"] = Label(_("Refresh"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "cancel": self.close, "red": self.close, "ok": self.open_selected,
            "green": self.open_selected,
            "up": self.up, "down": self.down,
        }, -1)
        self.setTitle(_("IPK/DEB and user scripts"))
        self.onShown.append(self.refresh)

    def refresh(self):
        try:
            idx = self["list"].getSelectedIndex()
            self["info"].setText(self.MENU[idx][1])
        except Exception:
            self["info"].setText("")
    def up(self):
        self["list"].up(); self.refresh()
    def down(self):
        self["list"].down(); self.refresh()
    def open_selected(self):
        index = self["list"].getSelectedIndex()
        self.session.open(GSUInfo, self.MENU[index][0],
                          package_center_selection_information(index))


class GSUWarderTools(Screen):
    """Modern diagnostics grouped behind the original GSU-style top level."""
    skin = """
    <screen name="GSUWarderTools" position="center,center" size="1050,690" title="Warder Diagnostics & Tools">
        <widget name="menu" position="35,35" size="980,570" font="Regular;27" itemHeight="42" />
        <widget name="key_red" position="35,625" size="250,45" font="Regular;24" foregroundColor="#ff3333" />
    </screen>
    """
    MENU = [
        (_("Health Check"), "healthcheck"),
        (_("Service Dashboard"), "servicedashboard"),
        (_("Network Health"), "nethealth"),
        (_("Network Mount Doctor"), "mountdoctor"),
        (_("Storage Health"), "storagehealth"),
        (_("Enigma2 Runtime Health"), "runtimehealth"),
        (_("Tuner information"), "tuners"),
        (_("Temperatures"), "temps"),
        (_("System & Hardware"), "system"),
        (_("Network & Interfaces"), "network"),
        (_("Storage & Filesystems"), "storage"),
        (_("Memory & Swap"), "memory"),
        (_("Services & Processes"), "services"),
        (_("Network Mounts (NFS/CIFS)"), "mounts"),
        (_("Logs & Diagnostics"), "logs"),
        (_("Create Diagnostic Bundle"), "diagbundle"),
    ]

    def __init__(self, session):
        Screen.__init__(self, session)
        self["menu"] = MenuList([item[0] for item in self.MENU])
        self["key_red"] = Label(_("Close"))
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.ok, "cancel": self.close, "red": self.close,
        }, -1)
        self.setTitle(_("Warder Diagnostics & Tools"))

    def ok(self):
        action = self.MENU[self["menu"].getSelectedIndex()][1]
        actions = {
            "system": (_("System & Hardware"), system_information),
            "temps": (_("Temperatures"), temperature_information),
            "network": (_("Network & Interfaces"), network_information),
            "nethealth": (_("Network Health"), network_health_information),
            "storage": (_("Storage & Filesystems"), storage_information),
            "storagehealth": (_("Storage Health"), storage_health_information),
            "memory": (_("Memory & Swap"), memory_information),
            "servicedashboard": (_("Service Dashboard"), service_dashboard_information),
            "services": (_("Services & Processes"), service_information),
            "runtimehealth": (_("Enigma2 Runtime Health"), runtime_health_information),
            "mounts": (_("Network Mounts"), mount_information),
            "mountdoctor": (_("Network Mount Doctor"), network_mount_doctor_information),
            "tuners": (_("Tuner information"), tuner_information),
            "logs": (_("Logs & Diagnostics"), log_information),
            "healthcheck": (_("Health Check"), health_check_information),
        }
        if action in actions:
            title, fnc = actions[action]
            self.session.open(GSUInfo, title, fnc())
        elif action == "diagbundle":
            try:
                path = create_diagnostic_bundle()
                self.session.open(MessageBox, _("Diagnostic bundle created:\n%s") % path,
                                  MessageBox.TYPE_INFO, timeout=10)
            except Exception as exc:
                self.session.open(MessageBox, _("Unable to create diagnostic bundle.\n\n%s") % exc,
                                  MessageBox.TYPE_ERROR, timeout=10)


def main(session, **kwargs):
    session.open(SysUtilMngMain)


def startViaMenu(menuid, **kwargs):
    if menuid == "setup":
        return [(_("Glass System Utility"), main, "glass_sys_utils", None)]
    return []


def Plugins(path=None, **kwargs):
    return [
        PluginDescriptor(name=_("Glass System Utility"),
                         description=_("Glass System Utility - Warder Evolution"),
                         where=PluginDescriptor.WHERE_PLUGINMENU, icon="SysMgt.png", fnc=main),
        PluginDescriptor(name="Glass System Utility",
                         description="Glass System Utility - Warder Evolution",
                         where=PluginDescriptor.WHERE_MENU, fnc=startViaMenu),
    ]
