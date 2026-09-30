"""Host-side checks for receiver capability and update safety helpers."""

import importlib.util
import json
import os
import sys
import types
import unittest
from unittest import mock


def _module(name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


class _DummyScreen(object):
    def __init__(self, *args, **kwargs):
        pass


plugins = _module("Plugins")
plugin_api = _module("Plugins.Plugin")
plugin_api.PluginDescriptor = type("PluginDescriptor", (), {})
screens = _module("Screens")
message_box = _module("Screens.MessageBox")
message_box.MessageBox = type("MessageBox", (), {"TYPE_INFO": 0, "TYPE_ERROR": 1, "TYPE_YESNO": 2})
screen_api = _module("Screens.Screen")
screen_api.Screen = _DummyScreen
components = _module("Components")
actions = _module("Components.ActionMap")
actions.ActionMap = type("ActionMap", (), {})
labels = _module("Components.Label")
labels.Label = type("Label", (), {})
scroll = _module("Components.ScrollLabel")
scroll.ScrollLabel = type("ScrollLabel", (), {})
menus = _module("Components.MenuList")
menus.MenuList = type("MenuList", (), {})

SOURCE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "GlassSysUtil", "plugin.py")
spec = importlib.util.spec_from_file_location("gsu_plugin_test_target", SOURCE)
gsu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gsu)


class _Response(object):
    def __init__(self, body, url=None, content_type="application/json"):
        self.body = body
        self.url = url
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        if size == -1:
            result, self.body = self.body, b""
            return result
        result, self.body = self.body[:size], self.body[size:]
        return result

    def geturl(self):
        return self.url


class CapabilitySafetyTests(unittest.TestCase):
    def test_thermal_millidegrees_are_normalized_and_deduplicated(self):
        paths = [("/sys/class/thermal/thermal_zone0/temp", "/sys/class/thermal/thermal_zone0/type"),
                 ("/sys/class/hwmon/hwmon0/temp1_input", "/sys/class/hwmon/hwmon0/temp1_label")]

        def read(path, default="N/A"):
            return {paths[0][0]: "73036", paths[0][1]: "soc-thermal",
                    paths[1][0]: "73036", paths[1][1]: "soc-thermal"}.get(path, default)

        with mock.patch.object(gsu, "_temperature_candidates", return_value=paths), \
                mock.patch.object(gsu, "_read_text", side_effect=read), \
                mock.patch.object(gsu.os.path, "isfile", return_value=True), \
                mock.patch.object(gsu.os.path, "realpath", return_value="/sys/devices/thermal/temp"):
            values = gsu._temperature_values()
        self.assertEqual(values, [("soc-thermal", 73.036)])

    def test_temperature_outside_reasonable_range_is_ignored(self):
        with mock.patch.object(gsu, "_temperature_candidates", return_value=[("/sensor/temp", "")]), \
                mock.patch.object(gsu, "_read_text", return_value="999000"), \
                mock.patch.object(gsu.os.path, "isfile", return_value=True):
            self.assertEqual(gsu._temperature_values(), [])

    def test_proc_cmdline_nuls_become_argument_boundaries(self):
        with mock.patch.object(gsu, "_read_text", return_value="/usr/bin/oscam\x00--config-dir\x00/etc/oscam\x00"):
            args = gsu._proc_cmdline("123")
        self.assertEqual(args, ["/usr/bin/oscam", "--config-dir", "/etc/oscam"])
        self.assertEqual(gsu._process_option([("123", args)], "--config-dir"), "/etc/oscam")

    def test_oscam_details_never_echo_full_process_arguments(self):
        argv = ["/usr/bin/oscam", "--user", "secret-user", "--password", "secret-pass",
                "--config-dir", "/tmp/oscam"]
        with mock.patch.object(gsu, "_find_processes", return_value=[("123", argv)]), \
                mock.patch.object(gsu.os.path, "isfile", return_value=False):
            report = gsu.oscam_information()
        self.assertIn("Process IDs: 123", report)
        self.assertNotIn("secret-user", report)
        self.assertNotIn("secret-pass", report)

    def test_package_screen_does_not_run_repository_upgrade_query(self):
        calls = []

        def run(argv, timeout=3):
            calls.append(argv)
            return "Version: 1\nStatus: install user installed"

        with mock.patch.object(gsu, "_run", side_effect=run):
            gsu.package_information()
        self.assertFalse(any("list-upgradable" in args for args in calls))


class UpdateManifestTests(unittest.TestCase):
    def _manifest(self, url=None, name=None):
        asset_name = name or "enigma2-plugin-glasssysutil_13.25-w6_all.ipk"
        asset_url = url or ("https://github.com/Evolution-by-Warder/Glass-System-Utility-Warder-Evolution/"
                            "releases/download/v13.25-w6/" + asset_name)
        body = json.dumps({"tag_name": "v13.25-w6", "assets": [
            {"name": asset_name, "browser_download_url": asset_url, "size": 1024}
        ]}).encode("utf-8")
        return _Response(body)

    def test_accepts_exact_official_asset_and_version(self):
        with mock.patch.object(gsu.urllib.request, "urlopen", return_value=self._manifest()):
            release = gsu._latest_release()
        self.assertEqual(release["version"], "13.25-w6")
        self.assertEqual(release["size"], 1024)

    def test_rejects_untrusted_redirect_origin_and_wrong_asset_name(self):
        malicious = "https://github.com.attacker.invalid/Evolution-by-Warder/Glass-System-Utility-Warder-Evolution/releases/download/v13.25-w6/enigma2-plugin-glasssysutil_13.25-w6_all.ipk"
        with mock.patch.object(gsu.urllib.request, "urlopen", return_value=self._manifest(url=malicious)):
            self.assertIsNone(gsu._latest_release())
        with mock.patch.object(gsu.urllib.request, "urlopen", return_value=self._manifest(name="other.ipk")):
            self.assertIsNone(gsu._latest_release())

    def test_package_version_mismatch_stops_before_opkg_install(self):
        release = {"version": "13.25-w6", "name": "enigma2-plugin-glasssysutil_13.25-w6_all.ipk"}
        calls = []

        def run(argv, timeout=3):
            calls.append(argv)
            return 0, "Package: enigma2-plugin-glasssysutil\nVersion: 13.25-w5"

        with mock.patch.object(gsu, "_download_update", return_value="/tmp/update.ipk"), \
                mock.patch.object(gsu, "_run_status", side_effect=run), \
                mock.patch.object(gsu.os, "unlink"):
            with self.assertRaises(ValueError):
                gsu._install_release(release)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:2], ["opkg", "info"])


if __name__ == "__main__":
    unittest.main()
