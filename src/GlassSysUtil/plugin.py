# -*- coding: utf-8 -*-
"""
Glass System Utility Warder Evolution
Modern source core. Original Glass System Utility authorship is respected.
"""

from __future__ import absolute_import

import os
import platform
import shutil
import socket
import subprocess
import json
import tempfile
import threading
import urllib.request
import urllib.error
from urllib.parse import urlsplit

from Plugins.Plugin import PluginDescriptor
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
_AUTO_UPDATE_STARTED = False


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
    rows.append("CPU: %s" % (cpu or "N/A"))
    # Serial is deliberately reported only as presence, not exposed in UI.
    serial_present = any(bool(_read_text(path, "")) for path in serial_paths)
    rows.append("Hardware serial interface: %s" % ("available (hidden)" if serial_present else "not exposed"))

    cpu_count = os.cpu_count()
    rows.append("CPU cores: %s" % (cpu_count if cpu_count is not None else "N/A"))

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
        rows.append("CPU frequency: %.0f-%.0f MHz" % (min(freq_values), max(freq_values)))

    return "\n".join(rows)


def system_information():
    model = _read_text("/proc/stb/info/model", platform.machine())
    brand = _read_text("/proc/stb/info/brand", "")
    image = _read_text("/etc/image-version", "N/A")
    cpu = "N/A"
    for line in _read_lines("/proc/cpuinfo"):
        if ":" in line and line.lower().startswith(("model name", "processor")):
            cpu = line.split(":", 1)[1].strip()
            if cpu:
                break
    return "\n".join((
        "Glass System Utility Warder Evolution %s" % VERSION, "",
        "Receiver: %s %s" % (brand, model),
        "Hostname: %s" % socket.gethostname(),
        "CPU: %s" % cpu,
        "Architecture: %s" % platform.machine(),
        "Kernel: %s" % platform.release(),
        "Python: %s" % platform.python_version(),
        "Uptime: %s" % _uptime(),
        "Image: %s" % image,
    ))


def network_information():
    rows = ["Default gateway: %s" % _default_gateway()]
    resolvers = []
    for line in _read_lines("/etc/resolv.conf"):
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "nameserver":
            resolvers.append(fields[1])
    rows.append("DNS: %s" % (", ".join(resolvers) if resolvers else "N/A"))
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
    rows = []
    matches = _find_processes("oscam")
    rows.append("Process: %s" % ("RUNNING" if matches else "not detected"))
    if matches:
        rows.append("Process IDs: %s" % ", ".join(pid for pid, argv in matches[:8]))
    config_dir = _process_option(matches, "--config-dir")

    if not config_dir:
        pidfiles = ("/var/tmp/oscam-uni.pid", "/var/volatile/tmp/oscam-uni.pid")
        for pidfile in pidfiles:
            if os.path.isfile(pidfile):
                rows.append("PID file: %s" % pidfile)
                break

    candidates = []
    if config_dir:
        candidates.append(os.path.join(config_dir, "oscam.conf"))
    candidates.extend([
        "/etc/tuxbox/config/oscam-uni/oscam.conf",
        "/etc/tuxbox/config/oscam.conf",
        "/etc/tuxbox/config/oscam/oscam.conf",
        "/usr/keys/oscam.conf",
        "/var/keys/oscam.conf",
    ])
    found = next((path for path in candidates if os.path.isfile(path)), "")
    rows.append("")
    rows.append("Config: %s" % (found if found else "not found"))
    if config_dir:
        rows.append("Config dir: %s" % config_dir)
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
        rows.append("Enigma2 tuner sockets")
        rows.extend(line.rstrip() for line in nim_sockets[:80])
    else:
        rows.append("Enigma2 tuner socket table: not exposed")

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
    rows += ["", "DVB device adapters: %s" %
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
    rows.append("Kernel log: %s" % ("available" if dmesg else "not available"))
    return "\n".join(rows) if rows else "No known diagnostic logs found."


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

def oscam_runtime_information():
    rows = []
    version_files = (
        "/var/volatile/tmp/.oscam/oscam.version",
        "/var/tmp/.oscam/oscam.version",
        "/tmp/.oscam/oscam.version",
    )
    version_file = next((path for path in version_files if os.path.isfile(path)), "")
    if version_file:
        rows.append("Runtime version file: %s" % version_file)
        for line in _read_lines(version_file)[:30]:
            text = line.strip()
            if text and not any(secret in text.lower() for secret in ("password", "passwd", "pwd=")):
                rows.append(text)
    else:
        rows.append("OSCam runtime version file: not found")

    matches = _find_processes("oscam")
    config_dir = _process_option(matches, "--config-dir")
    if config_dir:
        server = os.path.join(config_dir, "oscam.server")
        users = os.path.join(config_dir, "oscam.user")
        reader_count = sum(1 for line in _read_lines(server) if line.strip().lower() == "[reader]")
        user_count = sum(1 for line in _read_lines(users) if line.strip().lower() in ("[account]", "[user]"))
        rows += ["", "Readers configured: %d" % reader_count, "Accounts configured: %d" % user_count]
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
        rows.append("  Version: %s" % (version or "N/A"))
        rows.append("  Status: %s" % (status or "N/A"))
    rows += ["", "Available upgrades: not checked here (repository queries may block this screen)."]
    return "\n".join(rows)


def network_diagnostics():
    rows = []
    gateway = _default_gateway()
    rows.append("Default gateway: %s" % gateway)
    if gateway != "N/A":
        rc, ping = _run_status(["ping", "-c", "1", "-W", "2", gateway], 4)
        rows.append("Gateway reachability: %s" % ("OK" if rc == 0 else "no reply"))

    resolvers = []
    for line in _read_lines("/etc/resolv.conf"):
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "nameserver":
            resolvers.append(fields[1])
    rows.append("DNS servers: %s" % (", ".join(resolvers) if resolvers else "N/A"))

    route = _run(["ip", "route"], 4)
    if route:
        rows += ["", "Routes:"]
        rows.extend(route.splitlines()[:20])
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
    rows.append("Enigma2 binary: %s" % (_run(["which", "enigma2"], 3) or "not found"))
    rows.append("Python: %s" % platform.python_version())
    return "\n".join(rows)


def cam_inventory_information():
    rows = []
    init_root = "/etc/init.d"
    try:
        names = sorted(name for name in os.listdir(init_root) if "softcam" in name.lower() or "cam" in name.lower())
    except Exception:
        names = []
    if names:
        rows.append("Init scripts:")
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
        rows += ["", "Detected CAM binaries:"]
        rows.extend("  %s" % path for path in sorted(set(binaries))[:40])
    return "\n".join(rows) if rows else "No known CAM components detected."


def listening_ports_information():
    output = _run(["ss", "-lntup"], 5) or _run(["netstat", "-lntup"], 5)
    return "\n".join(output.splitlines()[:45]) if output else "No listener information available."


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
    rows = ["Detected runtime capabilities", ""]
    rows.extend("%-20s %s" % (name + ":", "YES" if present else "no") for name, present in probes)
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
                self.session.open(MessageBox, "Update check is unavailable on this Enigma2 image.",
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
                                  "Glass System Utility %s is up to date." % VERSION,
                                  MessageBox.TYPE_INFO, timeout=5)
            return
        self.release = release
        self.session.openWithCallback(
            self._answer, MessageBox,
            "Glass System Utility %s is available.\nInstalled: %s\n\nInstall the update now?"
            % (release["version"], VERSION), MessageBox.TYPE_YESNO)

    def _finish_check_error(self, detail):
        if not self.silent:
            self.session.open(MessageBox, "Unable to check for updates.\n\n%s" % detail,
                              MessageBox.TYPE_INFO, timeout=8)

    def _answer(self, answer):
        if not answer or not self.release:
            return
        if eTimer is None or not self._start_timer():
            self.session.open(MessageBox, "Update installation is unavailable on this Enigma2 image.",
                              MessageBox.TYPE_ERROR)
            return
        self.result = None
        self.progress = self.session.open(MessageBox, "Downloading, verifying and installing the update...",
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
            self._set_progress_text(progress, "Update installation failed.\n\n%s" % detail)
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
            progress.setTitle("Glass System Utility")
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


def _auto_update_check(session):
    """Start one non-blocking quiet check during this Enigma2 GUI session."""
    global _AUTO_UPDATE_STARTED
    if _AUTO_UPDATE_STARTED:
        return
    _AUTO_UPDATE_STARTED = True
    try:
        GSUUpdater(session).check(silent=True)
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


class SysUtilMngMain(Screen):
    skin = """
    <screen name="SysUtilMngMain" position="center,center" size="980,690" title="Glass System Utility Warder Evolution">
        <widget name="menu" position="35,35" size="910,610" font="Regular;28" itemHeight="46" />
    </screen>
    """
    MENU = [
        ("System & Hardware", "system"),
        ("Hardware Identity", "hardwareid"),
        ("Temperatures", "temps"),
        ("Network & Interfaces", "network"),
        ("Network Diagnostics", "netdiag"),
        ("Storage & Filesystems", "storage"),
        ("Filesystem Health", "fshealth"),
        ("Block Devices", "devices"),
        ("Memory & Swap", "memory"),
        ("Services & Processes", "services"),
        ("Listening Ports", "ports"),
        ("Network Mounts (NFS/CIFS)", "mounts"),
        ("CAM Inventory", "caminventory"),
        ("OSCam status", "oscam"),
        ("OSCam WebIF configuration", "oscamweb"),
        ("OSCam Runtime & Accounts", "oscamruntime"),
        ("Tuner information", "tuners"),
        ("Logs & Diagnostics", "logs"),
        ("Package information", "packages"),
        ("Image & Runtime", "imageinfo"),
        ("Diagnostic Summary", "summary"),
        ("Detected Capabilities", "capabilities"),
        ("Check for updates", "update"),
        ("Restart Enigma2 GUI", "restart"),
        ("About this build", "about"),
    ]

    def __init__(self, session):
        Screen.__init__(self, session)
        self["menu"] = MenuList([item[0] for item in self.MENU])
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.ok, "cancel": self.close}, -1)

    def _info(self, title, text):
        self.session.open(GSUInfo, title, text)

    def ok(self):
        index = self["menu"].getSelectedIndex()
        action = self.MENU[index][1]
        actions = {
            "system": ("System & Hardware", system_information),
            "hardwareid": ("Hardware Identity", hardware_identity_information),
            "temps": ("Temperatures", temperature_information),
            "network": ("Network & Interfaces", network_information),
            "netdiag": ("Network Diagnostics", network_diagnostics),
            "storage": ("Storage & Filesystems", storage_information),
            "fshealth": ("Filesystem Health", filesystem_health_information),
            "devices": ("Block Devices", device_information),
            "memory": ("Memory & Swap", memory_information),
            "services": ("Services & Processes", service_information),
            "ports": ("Listening Ports", listening_ports_information),
            "mounts": ("Network Mounts", mount_information),
            "caminventory": ("CAM Inventory", cam_inventory_information),
            "oscam": ("OSCam status", oscam_information),
            "oscamweb": ("OSCam WebIF configuration", oscam_webif_information),
            "oscamruntime": ("OSCam Runtime & Accounts", oscam_runtime_information),
            "tuners": ("Tuner information", tuner_information),
            "logs": ("Logs & Diagnostics", log_information),
            "packages": ("Package information", package_information),
            "imageinfo": ("Image & Runtime", image_information),
            "summary": ("Diagnostic Summary", diagnostic_summary),
            "capabilities": ("Detected Capabilities", capability_information),
        }
        if action in actions:
            title, fnc = actions[action]
            self._info(title, fnc())
        elif action == "update":
            GSUUpdater(self.session).check(silent=False)
        elif action == "restart":
            try:
                from Screens.Standby import TryQuitMainloop
                self.session.open(TryQuitMainloop, 3)
            except Exception as exc:
                self.session.open(MessageBox, str(exc), MessageBox.TYPE_ERROR)
        elif action == "about":
            self._info("About", (
                "Glass System Utility Warder Evolution %s\n\n"
                "Modern Python 3 source core.\n"
                "Read-only system, network, storage, service, mount, OSCam, tuner and log diagnostics enabled.\n\n"
                "State-changing legacy functions remain gated until separately migrated and tested."
            ) % VERSION)


def main(session, **kwargs):
    session.open(SysUtilMngMain)


def sessionAutostart(reason, **kwargs):
    # Network check only after Enigma2 session exists; failures stay silent.
    if reason == 0:
        session = kwargs.get("session")
        if session is not None:
            _auto_update_check(session)


def startViaMenu(menuid, **kwargs):
    if menuid == "setup":
        return [("Glass System Utility", main, "glass_sys_utils", None)]
    return []


def Plugins(path=None, **kwargs):
    return [
        PluginDescriptor(name="Glass System Utility",
                         description="Glass System Utility Warder Evolution",
                         where=PluginDescriptor.WHERE_PLUGINMENU, icon="SysMgt.png", fnc=main),
        PluginDescriptor(name="Glass System Utility",
                         description="Glass System Utility Warder Evolution",
                         where=PluginDescriptor.WHERE_MENU, fnc=startViaMenu),
        PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionAutostart),
    ]
