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
