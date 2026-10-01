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
import re
import tarfile
import time
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
        _oscam_find_scalar(flat, "lastchannel", "channel", "srvname", "servicename", "service"),
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


def oscam_live_rows():
    """Return sanitized, display-ready OSCam client rows plus a status message."""
    payload, reason = _oscam_live_status()
    if payload is None:
        return [], reason
    rows = []
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
            "address": _oscam_find_scalar(flat, "ip", "address", "host", "hostname"),
            "port": _oscam_find_scalar(flat, "port", "remoteport"),
            "protocol": _oscam_find_scalar(flat, "protocol", "proto"),
            "srvid": srvid,
            "caid": caid,
            "provid": provid,
            "channel": channel,
            "status": _oscam_find_scalar(flat, "status", "connection", "state"),
            "ecm": _oscam_normalize_ecm(_oscam_find_scalar(flat, "ecmtime", "ecm_time", "lastresponsetime", "lastresponse")),
            "idle": _oscam_normalize_idle(_oscam_find_scalar(flat, "idle", "idletime")),
        }
        if not _oscam_row_is_noise(row):
            rows.append(row)
    return rows, "" if rows else "API reachable, no useful client/reader rows recognized."


def _oscam_display(value):
    return "" if value in (None, "", "-") else str(value)


def _oscam_service_display(row):
    srvid, caid, provid = (_oscam_display(row[key]) for key in ("srvid", "caid", "provid"))
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
    ("name", 20, 210),
    ("address", 245, 190),
    ("port", 450, 75),
    ("protocol", 540, 120),
    ("service", 675, 230),
    ("channel", 920, 230),
    ("ecm", 1165, 95),
    ("idle", 1275, 80),
    ("status", 1370, 130),
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


def _oscam_status_display(row):
    status = _oscam_display(row.get("status"))
    if status:
        return status.upper()
    idle = _oscam_display(row.get("idle"))
    return "IDLE" if idle else ""


def _oscam_table_values(row):
    name = _oscam_display(row.get("name"))
    role = _oscam_row_role(row)
    if role.strip():
        name = "%s  %s" % (role, name)
    return {
        "name": name,
        "address": _oscam_display(row.get("address")),
        "port": _oscam_display(row.get("port")),
        "protocol": _oscam_display(row.get("protocol")),
        "service": _oscam_service_display(row),
        "channel": _oscam_display(row.get("channel")),
        "ecm": _oscam_display(row.get("ecm")),
        "idle": _oscam_display(row.get("idle")),
        "status": _oscam_status_display(row),
    }


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
    rows = ["GSU Health Check", ""]

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
        rows.append("[%s] Memory: %.0f%% available" % (state, pct))
    else:
        rows.append("[INFO] Memory: data not exposed")

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
        rows.append("[INFO] Storage: no physical filesystem mounts detected")

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
        rows.append("[PASS] Network link: %s" % ", ".join(up))
    elif interfaces:
        rows.append("[WARNING] Network link: no detected interface is up")
    else:
        rows.append("[INFO] Network link: interfaces not exposed")
    rows.append("[%s] Default gateway: %s" % ("PASS" if gateway and gateway != "N/A" else "INFO", gateway or "N/A"))
    rows.append("[%s] DNS configuration: %s" % (
        "PASS" if resolvers else "WARNING", ", ".join(resolvers) if resolvers else "no resolver configured"))

    # Enigma2 is expected while this screen is running; report rather than mutate anything.
    e2 = _find_processes("enigma2")
    rows.append("[%s] Enigma2 process: %s" % ("PASS" if e2 else "WARNING", "running" if e2 else "not detected"))

    temps = _temperature_values()
    if temps:
        hottest = max(value for label, value in temps)
        state = "PASS" if hottest < 80 else ("WARNING" if hottest < 95 else "WARNING")
        rows.append("[%s] Temperature: hottest detected %.1f C" % (state, hottest))
    else:
        rows.append("[INFO] Temperature: measurement not exposed")

    mounts = [line for line in _read_lines("/proc/mounts")
              if len(line.split()) >= 3 and line.split()[2].lower() in ("nfs", "nfs4", "cifs", "smbfs")]
    rows.append("[INFO] Network mounts: %d active" % len(mounts))

    cams = []
    for name in ("oscam", "ncam", "cccam", "mgcamd"):
        if _find_processes(name):
            cams.append(name)
    rows.append("[INFO] CAM: %s" % (", ".join(sorted(set(cams))) if cams else "no known CAM process detected"))

    nim = _read_lines("/proc/bus/nim_sockets")
    try:
        dvb = sorted(os.listdir("/sys/class/dvb"))
    except Exception:
        dvb = []
    if nim or dvb:
        rows.append("[PASS] Tuner interfaces: detected")
    else:
        rows.append("[INFO] Tuner interfaces: not exposed through detected system interfaces")

    rows += ["", "Health Check is read-only. INFO means a capability is absent, optional, or not enough evidence exists to call it a fault."]
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
            "Glass System Utility Warder Evolution diagnostic bundle\n"
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
        rows.append("Resident memory: %s" % status["VmRSS"])
    if status.get("VmSize"):
        rows.append("Virtual memory: %s" % status["VmSize"])
    seconds = _process_runtime_seconds(pid)
    if seconds is not None:
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        rows.append("Process runtime: %dd %02d:%02d:%02d" % (days, hours, minutes, seconds))
    return rows

def active_cam_summary():
    cam = _active_cam()
    if not cam:
        return "No known active CAM process detected."
    rows = [
        "Active CAM: %s" % cam["name"],
        "Family: %s" % cam["family"],
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



def time_health_information():
    """Report clock and detected time-sync facilities without assuming an image."""
    rows = ["Local time: %s" % time.strftime("%Y-%m-%d %H:%M:%S %Z")]
    rows.append("UTC time: %s" % time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

    detected = []
    for name in ("chronyd", "ntpd", "ntpdate", "systemd-timesyncd"):
        matches = _find_processes(name)
        if matches:
            detected.append("%s (running)" % name)
    for binary in ("chronyc", "ntpq", "timedatectl"):
        path = _run(["which", binary], 2)
        if path:
            detected.append("%s (available)" % binary)
    rows.append("Time sync: %s" % (", ".join(detected) if detected else "no known time-sync facility detected"))

    # Prefer status commands only when the corresponding client exists.
    chronyc = _run(["which", "chronyc"], 2)
    if chronyc:
        tracking = _run(["chronyc", "tracking"], 4)
        if tracking:
            rows += ["", "chrony tracking:"]
            rows.extend(tracking.splitlines()[:16])
    else:
        ntpq = _run(["which", "ntpq"], 2)
        if ntpq:
            peers = _run(["ntpq", "-pn"], 4)
            if peers:
                rows += ["", "NTP peers:"]
                rows.extend(peers.splitlines()[:16])
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



class GSUActiveCAM(Screen):
    """Visual OSCam/CAM monitor with a compact live table and safe actions."""
    skin = """
    <screen name="GSUActiveCAM" position="center,center" size="1500,760" title="Active CAM / OSCam Monitor">
        <widget name="summary" position="25,20" size="1450,105" font="Regular;22" />
        <widget name="live_status" position="25,128" size="1450,32" font="Regular;20" foregroundColor="#33cc33" />
        <widget name="h_name" position="45,170" size="210,34" font="Regular;18" foregroundColor="#e6d500" text="Reader / User" />
        <widget name="h_address" position="270,170" size="190,34" font="Regular;18" foregroundColor="#e6d500" text="Address" />
        <widget name="h_port" position="475,170" size="75,34" font="Regular;18" foregroundColor="#e6d500" text="Port" />
        <widget name="h_protocol" position="565,170" size="120,34" font="Regular;18" foregroundColor="#e6d500" text="Protocol" />
        <widget name="h_service" position="700,170" size="230,34" font="Regular;18" foregroundColor="#e6d500" text="srvid:caid@provid" />
        <widget name="h_channel" position="945,170" size="230,34" font="Regular;18" foregroundColor="#e6d500" text="Channel" />
        <widget name="h_ecm" position="1190,170" size="95,34" font="Regular;18" foregroundColor="#e6d500" text="ECM" />
        <widget name="h_idle" position="1300,170" size="80,34" font="Regular;18" foregroundColor="#e6d500" text="Idle" />
        <widget name="h_status" position="1395,170" size="105,34" font="Regular;18" foregroundColor="#e6d500" text="Status" />
        <widget source="table" render="Listbox" position="25,207" size="1450,445" scrollbarMode="showOnDemand">
            <convert type="TemplatedMultiContent">
                {"template": [MultiContentEntryText(pos=(20,0),size=(210,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=1),
                              MultiContentEntryText(pos=(245,0),size=(190,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=2),
                              MultiContentEntryText(pos=(450,0),size=(75,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=3),
                              MultiContentEntryText(pos=(540,0),size=(120,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=4),
                              MultiContentEntryText(pos=(675,0),size=(230,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=5),
                              MultiContentEntryText(pos=(920,0),size=(230,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=6),
                              MultiContentEntryText(pos=(1165,0),size=(95,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=7),
                              MultiContentEntryText(pos=(1275,0),size=(80,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=8),
                              MultiContentEntryText(pos=(1370,0),size=(130,34),font=0,flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER,text=9)],
                 "fonts":[gFont("Regular",18)],"itemHeight":34}
            </convert>
        </widget>
        <widget name="key_red" position="35,680" size="230,45" font="Regular;24" foregroundColor="#ff3333" />
        <widget name="key_green" position="380,680" size="250,45" font="Regular;24" foregroundColor="#33cc33" />
        <widget name="key_yellow" position="760,680" size="220,45" font="Regular;24" foregroundColor="#e6d500" />
        <widget name="key_blue" position="1180,680" size="220,45" font="Regular;24" foregroundColor="#3399ff" />
    </screen>
    """
    TABLE_HEADER = "  Reader/User     Address          Port   Protocol   srvid:caid@provid     Channel                  ECM       Idle      Status"

    def __init__(self, session):
        Screen.__init__(self, session)
        self["summary"] = Label(active_cam_summary())
        self["live_status"] = Label("")
        if List is not None:
            self["table"] = List([])
        else:
            self["table"] = MenuList([])
        self["key_red"] = Label("Close")
        command, detail = _active_cam_restart_command()
        self.restart_command = command
        self.restart_detail = detail
        self["key_green"] = Label("Restart CAM" if command else "Restart unavailable")
        self["key_yellow"] = Label("Refresh")
        self["key_blue"] = Label("Details")
        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions"], {
                "cancel": self.close,
                "red": self.close,
                "green": self.restart_cam,
                "yellow": self._refresh,
                "blue": self.show_details,
                "up": self["table"].up,
                "down": self["table"].down,
                "left": self["table"].pageUp,
                "right": self["table"].pageDown,
            }, -1)
        self._refresh_in_progress = False
        self._live_fetch_running = False
        self._closing_live_monitor = False
        self._refresh()
        self._start_auto_refresh()

    def _refresh(self):
        if getattr(self, "_refresh_in_progress", False):
            return
        self._refresh_in_progress = True
        try:
            try:
                self["summary"].setText(active_cam_summary())
            except Exception:
                pass
            active = _active_cam()
            table_rows, reason = ([], "No supported active OSCam detected.")
            if active and active.get("family") == "oscam":
                table_rows, reason = oscam_live_rows()
            try:
                selected = 0
                try:
                    selected = self["table"].getSelectionIndex()
                except Exception:
                    pass
                self["table"].setList([tuple([row] + list(_oscam_table_values(row).values())) for row in table_rows] if List is not None else [_oscam_table_line(row) for row in table_rows])
                if table_rows:
                    try:
                        self["table"].moveToIndex(min(selected, len(table_rows) - 1))
                    except Exception:
                        pass
                    self["live_status"].setText("Live OSCam: %d row%s | mapped %s" %
                                                (len(table_rows), "" if len(table_rows) == 1 else "s",
                                                 _oscam_live_quality(table_rows)))
                else:
                    self["live_status"].setText("Live OSCam: %s" % reason)
            except Exception:
                pass
            command, detail = _active_cam_restart_command()
            self.restart_command = command
            self.restart_detail = detail
            try:
                self["key_green"].setText("Restart CAM" if command else "Restart unavailable")
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
                if getattr(self, "_closing_live_monitor", False):
                    self._live_fetch_running = False
                    return
                try:
                    selected = 0
                    try:
                        selected = self["table"].getSelectionIndex()
                    except Exception:
                        pass
                    self["table"].setList([tuple([row] + list(_oscam_table_values(row).values())) for row in rows] if List is not None else [_oscam_table_line(row) for row in rows])
                    if rows:
                        try:
                            self["table"].moveToIndex(min(selected, len(rows) - 1))
                        except Exception:
                            pass
                        self["live_status"].setText("Live OSCam: %d row%s | mapped %s" %
                                                    (len(rows), "" if len(rows) == 1 else "s",
                                                     _oscam_live_quality(rows)))
                    else:
                        self["live_status"].setText("Live OSCam: %s" % reason)
                    try:
                        self["summary"].setText(active_cam_summary())
                    except Exception:
                        pass
                finally:
                    self._live_fetch_running = False

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
        timer = getattr(self, "_live_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        return Screen.close(self, *args, **kwargs)

    def show_details(self):
        active = _active_cam()
        if not active:
            self.session.open(MessageBox, "No supported active CAM detected.", MessageBox.TYPE_INFO, timeout=6)
            return
        parts = [active_cam_information()]
        if active.get("family") == "oscam":
            parts.extend(["", oscam_live_information(), "", oscam_runtime_information(), "",
                          oscam_webif_information(), "", oscam_api_schema_information()])
        self.session.open(GSUInfo, "CAM / OSCam Details", "\n".join(parts))

    def restart_cam(self):
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
                self._refresh()
                if rc != 0:
                    detail = output[-800:] if output else "restart command returned status %s" % rc
                    self.session.open(MessageBox, "Active CAM restart failed.\n\n%s" % detail,
                                      MessageBox.TYPE_ERROR, timeout=10)
                elif verified:
                    changed = " (new PID %s)" % verified["pid"] if verified["pid"] != before_pid else ""
                    self.session.open(MessageBox, "Active CAM restart verified%s." % changed,
                                      MessageBox.TYPE_INFO, timeout=6)
                else:
                    self.session.open(MessageBox,
                                      "Restart command completed, but no active CAM was detected afterwards.",
                                      MessageBox.TYPE_ERROR, timeout=10)

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

        threading.Thread(target=worker, name="GSU-CAM-Restart", daemon=True).start()

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
        ("Time & Synchronization", "timehealth"),
        ("Storage & Filesystems", "storage"),
        ("Filesystem Health", "fshealth"),
        ("Block Devices", "devices"),
        ("Memory & Swap", "memory"),
        ("Services & Processes", "services"),
        ("Listening Ports", "ports"),
        ("Network Mounts (NFS/CIFS)", "mounts"),
        ("CAM Inventory", "caminventory"),
        ("Active CAM / OSCam Monitor", "cammonitor"),

        ("Tuner information", "tuners"),
        ("Logs & Diagnostics", "logs"),
        ("Package information", "packages"),
        ("Image & Runtime", "imageinfo"),
        ("Diagnostic Summary", "summary"),
        ("Health Check", "healthcheck"),
        ("Create Diagnostic Bundle", "diagbundle"),
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
            "timehealth": ("Time & Synchronization", time_health_information),
            "storage": ("Storage & Filesystems", storage_information),
            "fshealth": ("Filesystem Health", filesystem_health_information),
            "devices": ("Block Devices", device_information),
            "memory": ("Memory & Swap", memory_information),
            "services": ("Services & Processes", service_information),
            "ports": ("Listening Ports", listening_ports_information),
            "mounts": ("Network Mounts", mount_information),
            "caminventory": ("CAM Inventory", cam_inventory_information),

            "tuners": ("Tuner information", tuner_information),
            "logs": ("Logs & Diagnostics", log_information),
            "packages": ("Package information", package_information),
            "imageinfo": ("Image & Runtime", image_information),
            "summary": ("Diagnostic Summary", diagnostic_summary),
            "healthcheck": ("Health Check", health_check_information),
            "capabilities": ("Detected Capabilities", capability_information),
        }
        if action in actions:
            title, fnc = actions[action]
            self._info(title, fnc())
        elif action == "cammonitor":
            self.session.open(GSUActiveCAM)
        elif action == "diagbundle":
            try:
                path = create_diagnostic_bundle()
                self.session.open(MessageBox, "Diagnostic bundle created:\n%s" % path,
                                  MessageBox.TYPE_INFO, timeout=10)
            except Exception as exc:
                self.session.open(MessageBox, "Unable to create diagnostic bundle.\n\n%s" % exc,
                                  MessageBox.TYPE_ERROR, timeout=10)
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
