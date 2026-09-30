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

from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

VERSION = "13.22-w3"


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
        ("Network & Interfaces", "network"),
        ("Storage & Filesystems", "storage"),
        ("Memory & Swap", "memory"),
        ("Services & Processes", "services"),
        ("Network Mounts (NFS/CIFS)", "mounts"),
        ("OSCam status", "oscam"),
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
            "network": ("Network & Interfaces", network_information),
            "storage": ("Storage & Filesystems", storage_information),
            "memory": ("Memory & Swap", memory_information),
            "services": ("Services & Processes", service_information),
            "mounts": ("Network Mounts", mount_information),
            "oscam": ("OSCam status", oscam_information),
        }
        if action in actions:
            title, fnc = actions[action]
            self._info(title, fnc())
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
                "Read-only system, network, storage, service, mount and OSCam diagnostics enabled.\n\n"
                "State-changing legacy functions remain gated until separately migrated and tested."
            ) % VERSION)


def main(session, **kwargs):
    session.open(SysUtilMngMain)


def startViaMenu(menuid, **kwargs):
    if menuid == "setup":
        return [("Glass System Utility", main, "glass_sys_utils", None)]
    return []


def Plugins(path=None, **kwargs):
    return [
        PluginDescriptor(name="Glass System Utility",
                         description="Glass System Utility Warder Evolution",
                         where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main),
        PluginDescriptor(name="Glass System Utility",
                         description="Glass System Utility Warder Evolution",
                         where=PluginDescriptor.WHERE_MENU, fnc=startViaMenu),
    ]
