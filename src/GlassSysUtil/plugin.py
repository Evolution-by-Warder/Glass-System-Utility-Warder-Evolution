# -*- coding: utf-8 -*-
"""
Glass System Utility Warder Evolution

Modern source-core baseline. Original Glass System Utility authorship is
respected; Warder Evolution identifies the modernization work.
"""

from __future__ import absolute_import

import os
import platform
import shutil
import socket
import time

from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList


VERSION = "13.21-w2"


def _read_text(path, default="N/A"):
    try:
        with open(path, "r") as handle:
            value = handle.read().strip()
        return value or default
    except Exception:
        return default


def _uptime():
    try:
        seconds = int(float(_read_text("/proc/uptime", "0").split()[0]))
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, _ = divmod(seconds, 60)
        return "%dd %02d:%02d" % (days, hours, minutes)
    except Exception:
        return "N/A"


def system_information():
    image = _read_text("/etc/image-version", "N/A")
    model = _read_text("/proc/stb/info/model", platform.machine())
    return "\n".join((
        "Glass System Utility Warder Evolution %s" % VERSION,
        "",
        "Model: %s" % model,
        "Hostname: %s" % socket.gethostname(),
        "Kernel: %s" % platform.release(),
        "Python: %s" % platform.python_version(),
        "Uptime: %s" % _uptime(),
        "Image: %s" % image,
    ))


def network_information():
    root = "/sys/class/net"
    rows = []
    try:
        names = sorted(os.listdir(root))
    except Exception:
        names = []
    for name in names:
        state = _read_text(os.path.join(root, name, "operstate"), "unknown")
        mac = _read_text(os.path.join(root, name, "address"), "N/A")
        rows.append("%s: %s  %s" % (name, state, mac))
    return "\n".join(rows) if rows else "No network interfaces found."


def storage_information():
    rows = []
    seen = set()
    try:
        with open("/proc/mounts", "r") as handle:
            mounts = handle.readlines()
    except Exception:
        mounts = []
    for line in mounts:
        fields = line.split()
        if len(fields) < 2:
            continue
        device, mountpoint = fields[:2]
        if mountpoint in seen or not device.startswith("/dev/"):
            continue
        seen.add(mountpoint)
        try:
            usage = shutil.disk_usage(mountpoint)
            rows.append("%s  %s\n  %.1f / %.1f GiB used" % (
                device, mountpoint,
                (usage.total - usage.free) / float(1024 ** 3),
                usage.total / float(1024 ** 3)))
        except Exception:
            rows.append("%s  %s" % (device, mountpoint))
    return "\n\n".join(rows) if rows else "No physical storage mounts found."


def memory_information():
    wanted = ("MemTotal", "MemAvailable", "MemFree", "SwapTotal", "SwapFree")
    values = {}
    try:
        with open("/proc/meminfo", "r") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                if key in wanted:
                    values[key] = value.strip()
    except Exception:
        pass
    return "\n".join("%s: %s" % (key, values.get(key, "N/A")) for key in wanted)


class GSUInfo(Screen):
    skin = """
    <screen name="GSUInfo" position="center,center" size="1050,620" title="Glass System Utility">
        <widget name="text" position="30,30" size="990,560" font="Regular;26" />
    </screen>
    """

    def __init__(self, session, title, text):
        Screen.__init__(self, session)
        self.setTitle(title)
        self["text"] = Label(text)
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.close,
            "cancel": self.close,
        }, -1)


class SysUtilMngMain(Screen):
    skin = """
    <screen name="SysUtilMngMain" position="center,center" size="900,600" title="Glass System Utility Warder Evolution">
        <widget name="menu" position="30,30" size="840,520" font="Regular;28" itemHeight="44" />
    </screen>
    """

    MENU = [
        ("System information", "system"),
        ("Network information", "network"),
        ("Storage information", "storage"),
        ("Memory information", "memory"),
        ("Restart Enigma2 GUI", "restart"),
        ("About this build", "about"),
    ]

    def __init__(self, session):
        Screen.__init__(self, session)
        self["menu"] = MenuList([item[0] for item in self.MENU])
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.ok,
            "cancel": self.close,
        }, -1)

    def ok(self):
        index = self["menu"].getSelectedIndex()
        action = self.MENU[index][1]
        if action == "system":
            self.session.open(GSUInfo, "System information", system_information())
        elif action == "network":
            self.session.open(GSUInfo, "Network information", network_information())
        elif action == "storage":
            self.session.open(GSUInfo, "Storage information", storage_information())
        elif action == "memory":
            self.session.open(GSUInfo, "Memory information", memory_information())
        elif action == "restart":
            try:
                from Screens.Standby import TryQuitMainloop
                self.session.open(TryQuitMainloop, 3)
            except Exception as exc:
                self.session.open(MessageBox, str(exc), MessageBox.TYPE_ERROR)
        elif action == "about":
            text = (
                "Glass System Utility Warder Evolution %s\n\n"
                "Modern Python 3 source-core baseline.\n"
                "No minor-version-specific bytecode selection.\n\n"
                "Legacy write, CAM and mount functions are migrated separately."
            ) % VERSION
            self.session.open(GSUInfo, "About", text)


def main(session, **kwargs):
    session.open(SysUtilMngMain)


def Plugins(path=None, **kwargs):
    return [
        PluginDescriptor(
            name="Glass System Utility",
            description="Glass System Utility Warder Evolution",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main,
        )
    ]
