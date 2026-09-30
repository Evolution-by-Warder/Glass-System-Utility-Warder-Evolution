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
import urllib.request
import urllib.error

from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

VERSION = "13.24-w5"
UPDATE_API = "https://api.github.com/repos/Evolution-by-Warder/Glass-System-Utility-Warder-Evolution/releases/latest"
UPDATE_MARKER = "/tmp/gsu-update-check"


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
    proc = _run(["ps", "-ef"], 4) or _run(["pgrep", "-a", "-f", "."], 4)
    for line in proc.splitlines():
        low = line.lower()
        if any(name in low for name in patterns) and "grep" not in low:
            rows.append(line.strip())
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
    proc = _run(["pgrep", "-a", "-i", "oscam"], 4)
    matches = [line.strip() for line in proc.splitlines() if line.strip()]
    rows.append("Process: %s" % ("RUNNING" if matches else "not detected"))
    if matches:
        rows.extend(matches[:6])

    config_dir = ""
    for line in matches:
        fields = line.split()
        for index, field in enumerate(fields):
            if field == "--config-dir" and index + 1 < len(fields):
                config_dir = fields[index + 1]
                break
            if field.startswith("--config-dir="):
                config_dir = field.split("=", 1)[1]
                break
        if config_dir:
            break

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
    return raw.replace("\\x00", " ").strip()


def _find_processes(needle):
    rows = []
    try:
        pids = [name for name in os.listdir("/proc") if name.isdigit()]
    except Exception:
        pids = []
    for pid in pids:
        cmd = _proc_cmdline(pid)
        if needle.lower() in cmd.lower():
            rows.append((pid, cmd))
    return rows


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
    proc = _run(["pgrep", "-a", "-i", "oscam"], 4)
    matches = [line.strip() for line in proc.splitlines() if line.strip()]
    config_dir = ""
    for line in matches:
        fields = line.split()
        for index, field in enumerate(fields):
            if field == "--config-dir" and index + 1 < len(fields):
                config_dir = fields[index + 1]
                break
            if field.startswith("--config-dir="):
                config_dir = field.split("=", 1)[1]
                break
        if config_dir:
            break
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
    rows = []
    nim_root = "/proc/stb/frontend"
    try:
        frontends = sorted(os.listdir(nim_root))
    except Exception:
        frontends = []
    if frontends:
        rows.append("Frontend devices: %s" % ", ".join(frontends))
    nim_sockets = _read_lines("/proc/bus/nim_sockets")
    if nim_sockets:
        rows.append("")
        rows.extend(line.rstrip() for line in nim_sockets[:40])
    return "\n".join(rows) if rows else "No tuner information exposed by this image."


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


def temperature_information():
    rows = []
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
            rows.append("%s: %.1f C" % (label, value))
        except Exception:
            pass

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

    proc = _run(["pgrep", "-a", "-i", "oscam"], 4)
    matches = [line.strip() for line in proc.splitlines() if line.strip()]
    config_dir = ""
    for line in matches:
        fields = line.split()
        for index, field in enumerate(fields):
            if field == "--config-dir" and index + 1 < len(fields):
                config_dir = fields[index + 1]
                break
            if field.startswith("--config-dir="):
                config_dir = field.split("=", 1)[1]
                break
        if config_dir:
            break
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
    upgradable = _run(["opkg", "list-upgradable"], 8)
    count = len([line for line in upgradable.splitlines() if " - " in line])
    rows += ["", "Packages with upgrades available: %d" % count]
    return "\n".join(rows)


def network_diagnostics():
    rows = []
    gateway = _default_gateway()
    rows.append("Default gateway: %s" % gateway)
    if gateway != "N/A":
        ping = _run(["ping", "-c", "1", "-W", "2", gateway], 4)
        rows.append("Gateway reachability: %s" % ("OK" if "1 packets received" in ping or "1 received" in ping else "no reply"))

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


def diagnostic_summary():
    oscam = bool(_run(["pgrep", "-a", "-i", "oscam"], 3))
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
    """Compare Warder versions such as 13.24-w5 without float conversion."""
    text = (value or "").strip().lower().lstrip("v")
    parts = []
    for chunk in text.replace("-", ".").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _latest_release():
    """Read the public GitHub release manifest. No GitHub credentials are used."""
    try:
        req = urllib.request.Request(
            UPDATE_API,
            headers={"User-Agent": "Glass-System-Utility-Warder-Evolution/%s" % VERSION,
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
        tag = (data.get("tag_name") or "").strip()
        assets = data.get("assets") or []
        ipk = next((asset for asset in assets
                    if (asset.get("name") or "").endswith(".ipk")
                    and asset.get("browser_download_url")), None)
        if not tag or not ipk:
            return None
        return {"version": tag.lstrip("v"),
                "url": ipk.get("browser_download_url"),
                "name": ipk.get("name")}
    except Exception:
        return None


def _download_update(url, name):
    """Download only an IPK asset from this project's official GitHub releases."""
    if not url or not url.startswith("https://github.com/Evolution-by-Warder/Glass-System-Utility-Warder-Evolution/releases/download/"):
        return ""
    safe = os.path.basename(name or "")
    if not safe.endswith(".ipk"):
        return ""
    target = os.path.join("/tmp", safe)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Glass-System-Utility-Warder-Evolution/%s" % VERSION})
        with urllib.request.urlopen(req, timeout=20) as response, open(target, "wb") as handle:
            shutil.copyfileobj(response, handle)
        return target if os.path.isfile(target) and os.path.getsize(target) > 0 else ""
    except Exception:
        try:
            os.unlink(target)
        except Exception:
            pass
        return ""


class GSUUpdater(object):
    def __init__(self, session):
        self.session = session
        self.release = None

    def check(self, silent=True):
        release = _latest_release()
        if not release or _version_key(release["version"]) <= _version_key(VERSION):
            if not silent:
                self.session.open(MessageBox,
                                  "Glass System Utility %s is up to date." % VERSION,
                                  MessageBox.TYPE_INFO, timeout=5)
            return
        self.release = release
        self.session.openWithCallback(
            self._answer,
            MessageBox,
            "Glass System Utility %s is available.\nInstalled: %s\n\nInstall the update now?"
            % (release["version"], VERSION),
            MessageBox.TYPE_YESNO)

    def _answer(self, answer):
        if not answer or not self.release:
            return
        path = _download_update(self.release["url"], self.release["name"])
        if not path:
            self.session.open(MessageBox, "Update download failed.", MessageBox.TYPE_ERROR)
            return
        result = _run(["opkg", "install", path], 60)
        if "error" in result.lower() or "failed" in result.lower():
            self.session.open(MessageBox, "Update installation failed.\n\n%s" % result[-1200:],
                              MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(
            self._restart_after_update,
            MessageBox,
            "Update installed successfully.\nEnigma2 GUI will restart in 3 seconds.",
            MessageBox.TYPE_INFO,
            timeout=3)

    def _restart_after_update(self, *args):
        try:
            from Screens.Standby import TryQuitMainloop
            self.session.open(TryQuitMainloop, 3)
        except Exception as exc:
            self.session.open(MessageBox,
                              "Update is installed, but automatic GUI restart failed.\n\n%s" % exc,
                              MessageBox.TYPE_ERROR)


def _auto_update_check(session):
    """Once per GUI boot, check quietly and prompt only when a newer release exists."""
    try:
        if os.path.exists(UPDATE_MARKER):
            return
        with open(UPDATE_MARKER, "w") as handle:
            handle.write(VERSION)
        GSUUpdater(session).check(silent=True)
    except Exception:
        pass

class GSUInfo(Screen):
    skin = """
    <screen name="GSUInfo" position="center,center" size="1160,680" title="Glass System Utility">
        <widget name="text" position="30,30" size="1100,620" font="Regular;25" />
    </screen>
    """
    def __init__(self, session, title, text):
        Screen.__init__(self, session)
        self.setTitle(title)
        self["text"] = Label(text)
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.close, "cancel": self.close}, -1)


class SysUtilMngMain(Screen):
    skin = """
    <screen name="SysUtilMngMain" position="center,center" size="980,690" title="Glass System Utility Warder Evolution">
        <widget name="menu" position="35,35" size="910,610" font="Regular;28" itemHeight="46" />
    </screen>
    """
    MENU = [
        ("System & Hardware", "system"),
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
