import importlib.util
import os
import sys
import tempfile
import types
import unittest


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _Dummy(object):
    TYPE_INFO = 0
    TYPE_ERROR = 1
    TYPE_YESNO = 2


for package in ("Plugins", "Screens", "Components"):
    _stub(package)
_stub("Plugins.Plugin", PluginDescriptor=type("PluginDescriptor", (), {"WHERE_PLUGINMENU": 1, "WHERE_MENU": 2, "WHERE_SESSIONSTART": 3}))
_stub("Screens.MessageBox", MessageBox=_Dummy)
_stub("Screens.Screen", Screen=object)
_stub("Components.ActionMap", ActionMap=_Dummy)
_stub("Components.Label", Label=_Dummy)
_stub("Components.ScrollLabel", ScrollLabel=_Dummy)
_stub("Components.MenuList", MenuList=_Dummy)

PLUGIN = os.path.join(os.path.dirname(__file__), "..", "src", "GlassSysUtil", "plugin.py")
spec = importlib.util.spec_from_file_location("gsu_plugin_diag", PLUGIN)
gsu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gsu)


class DiagnosticRedactionTests(unittest.TestCase):
    def test_redacts_credentials_but_keeps_mac(self):
        source = "username = admin\npassword = secret\nMAC: aa:bb:cc:dd:ee:ff\n"
        result = gsu._redact_diagnostic_text(source)
        self.assertNotIn("admin", result)
        self.assertNotIn("secret", result)
        self.assertIn("aa:bb:cc:dd:ee:ff", result)
        self.assertIn("<redacted>", result)
        self.assertNotIn("<redacted-mac>", result)

    def test_redacts_stable_private_identifiers(self):
        source = "serial=ABC123\nuuid=deadbeef\nmachine-id=xyz987\n"
        result = gsu._redact_diagnostic_text(source)
        self.assertNotIn("ABC123", result)
        self.assertNotIn("deadbeef", result)
        self.assertNotIn("xyz987", result)
        self.assertEqual(result.count("<redacted-identifier>"), 3)


    def test_cam_restart_has_no_killall_fallback(self):
        import inspect
        source = inspect.getsource(gsu._active_cam_restart_command)
        self.assertNotIn('["killall"', source)
        self.assertIn("/etc/init.d/softcam", source)


    def test_cam_monitor_requires_confirmation_and_image_restart_path(self):
        with open(PLUGIN, "r", encoding="utf-8") as handle:
            source = handle.read()
        start = source.index("class GSUActiveCAM")
        end = source.index("class SysUtilMngMain", start)
        monitor = source[start:end]
        self.assertIn("openWithCallback", monitor)
        self.assertIn("_active_cam_restart_command", monitor)
        self.assertNotIn('["killall"', monitor)
        self.assertIn("threading.Thread", monitor)
        self.assertIn("GSU-CAM-Restart", monitor)
        self.assertIn('"yellow": self._refresh', monitor)
        self.assertIn('"blue": self.show_details', monitor)
        self.assertIn("oscam_runtime_information()", monitor)


    def test_process_runtime_uses_proc_starttime_not_directory_ctime(self):
        import inspect
        source = inspect.getsource(gsu._process_runtime_seconds)
        self.assertIn("/proc/%s/stat", source)
        self.assertIn("/proc/uptime", source)
        self.assertNotIn("st_ctime", source)

    def test_bundle_manifest_matches_practical_privacy_policy(self):
        import inspect
        source = inspect.getsource(gsu.create_diagnostic_bundle)
        self.assertIn("diagnostic LAN/MAC data is preserved", source)
        self.assertNotIn("MAC addresses and stable identifiers are redacted", source)

    def test_rejects_binary_or_oversized_log(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
            handle.write(b"abc\x00def")
        try:
            self.assertEqual(gsu._safe_diagnostic_file(path), "")
        finally:
            os.unlink(path)

        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
            handle.write(b"x" * 33)
        try:
            self.assertEqual(gsu._safe_diagnostic_file(path, limit=32), "")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()


class OSCamW11ReleaseContractTests(unittest.TestCase):
    def test_oscam_w11_fixed_table_contract(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("class GSUActiveCAM")
        end = source.index("class SysUtilMngMain", start)
        monitor = source[start:end]
        self.assertNotIn('<widget name="h_', monitor)
        self.assertNotIn('<widget name="sep', monitor)
        self.assertGreaterEqual(monitor.count("<eLabel"), 17)
        self.assertIn('source="table" render="Listbox"', monitor)
        self.assertIn("TemplatedMultiContent", monitor)

    def test_oscam_tuple_keeps_row_and_nine_columns(self):
        row = {"name": "reader1", "address": "192.168.10.6", "port": "3333",
               "protocol": "cs378x", "srvid": "3C3C", "caid": "0668",
               "provid": "000000", "channel": "Example TV", "ecm": "115 ms",
               "idle": "7s", "status": "CONNECTED"}
        item = gsu._oscam_list_tuple(row)
        self.assertEqual(len(item), 10)
        self.assertIs(item[0], row)
        self.assertEqual(item[1:], ("reader1", "192.168.10.6", "3333", "cs378x",
                                   "3C3C:0668@000000", "Example TV", "115 ms", "7s", "CONNECTED"))

    def test_w11_release_identity_is_consistent(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        version = open(os.path.join(root, "src", "GlassSysUtil", "version"), encoding="utf-8").read().strip()
        control = open(os.path.join(root, "packaging", "CONTROL", "control"), encoding="utf-8").read()
        postinst = open(os.path.join(root, "packaging", "CONTROL", "postinst"), encoding="utf-8").read()
        self.assertEqual(version, "13.31-w12")
        self.assertIn("Version: " + version, control)
        self.assertIn(version, postinst)


class OSCamReceiverPolishTests(unittest.TestCase):
    def test_current_service_fallback_is_dvbapi_scoped(self):
        old = gsu._current_service_name
        try:
            gsu._current_service_name = lambda: "DOMA"
            self.assertEqual(gsu._oscam_row_channel({"protocol": "dvbapi (client)", "type": "client"}), "DOMA")
            self.assertEqual(gsu._oscam_row_channel({"protocol": "cs378x", "type": "reader"}), "")
            self.assertEqual(gsu._oscam_row_channel({"protocol": "dvbapi", "channel": "API Name"}), "API Name")
        finally:
            gsu._current_service_name = old

    def test_status_column_has_more_room_than_reader_column(self):
        source = open(PLUGIN, encoding="utf-8").read()
        self.assertIn('("name", 20, 165)', source)
        self.assertIn('("status", 1325, 175)', source)
        self.assertIn('position="1350,170" size="150,34"', source)
