import importlib.util
import os
import re
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
_stub("Plugins.Plugin", PluginDescriptor=type("PluginDescriptor", (), {"WHERE_PLUGINMENU": 1, "WHERE_MENU": 2}))
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

    def test_release_identity_is_consistent(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        version = open(os.path.join(root, "src", "GlassSysUtil", "version"), encoding="utf-8").read().strip()
        control = open(os.path.join(root, "packaging", "CONTROL", "control"), encoding="utf-8").read()
        postinst = open(os.path.join(root, "packaging", "CONTROL", "postinst"), encoding="utf-8").read()
        self.assertEqual(version, "13.36-w17")
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


class ServiceDashboardTests(unittest.TestCase):
    def test_dashboard_is_read_only_and_bounded(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("def service_dashboard_information")
        end = source.index("def listening_ports_information", start)
        body = source[start:end]
        self.assertIn("_active_cam()", body)
        self.assertIn("/proc/mounts", body)
        self.assertIn('["ss", "-lntup"]', body)
        self.assertNotIn("restart", body.lower())
        self.assertNotIn("kill", body.lower())

    def test_dashboard_is_wired_once_in_main_menu(self):
        source = open(PLUGIN, encoding="utf-8").read()
        self.assertEqual(source.count('(_("Service Dashboard"), "servicedashboard")'), 1)
        self.assertEqual(source.count('"servicedashboard": (_("Service Dashboard"), service_dashboard_information)'), 1)

    def test_dashboard_accepts_capability_cam_record(self):
        old_cam = gsu._active_cam
        old_find = gsu._find_processes
        old_lines = gsu._read_lines
        old_run = gsu._run
        try:
            gsu._active_cam = lambda: {
                "family": "oscam", "name": "oscam", "pid": 4321,
                "matches": [(4321, ["/usr/bin/oscam"])]
            }
            gsu._find_processes = lambda needle: [(111, ["/usr/bin/enigma2"])] if needle == "enigma2" else []
            gsu._read_lines = lambda path: []
            gsu._run = lambda argv, timeout=3: ""
            text = gsu.service_dashboard_information()
            self.assertIn("[RUNNING] CAM       oscam  PID 4321", text)
        finally:
            gsu._active_cam = old_cam
            gsu._find_processes = old_find
            gsu._read_lines = old_lines
            gsu._run = old_run


class StorageHealthTests(unittest.TestCase):
    def test_storage_health_is_read_only_and_actionable(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("def storage_health_information")
        end = source.index("def filesystem_health_information", start)
        body = source[start:end]
        self.assertIn("shutil.disk_usage", body)
        self.assertIn("free_pct < 5", body)
        self.assertIn("read-only", body)
        self.assertNotIn("mkfs", body)
        self.assertNotIn("fsck", body)

    def test_storage_health_menu_wiring(self):
        source = open(PLUGIN, encoding="utf-8").read()
        self.assertEqual(source.count('(_("Storage Health"), "storagehealth")'), 1)
        self.assertEqual(source.count('"storagehealth": (_("Storage Health"), storage_health_information)'), 1)


class OperationalDoctorsTests(unittest.TestCase):
    def test_mount_doctor_never_reads_mount_configuration_contents(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("def network_mount_doctor_information")
        end = source.index("def time_health_information", start)
        body = source[start:end]
        self.assertIn("/proc/mounts", body)
        self.assertIn("mount.cifs", body)
        self.assertIn("/etc/fstab", body)
        self.assertNotIn('_read_lines("/etc/fstab")', body)
        self.assertNotIn("password", body.lower())

    def test_runtime_health_is_procfs_read_only(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("def runtime_health_information")
        end = source.index("def device_information", start)
        body = source[start:end]
        self.assertIn('/proc/%s/status', body)
        self.assertIn('/proc/%s/fd', body)
        self.assertNotIn("kill", body.lower())
        self.assertNotIn("remove(", body)

    def test_operational_doctors_are_wired_once(self):
        source = open(PLUGIN, encoding="utf-8").read()
        self.assertEqual(source.count('(_("Network Mount Doctor"), "mountdoctor")'), 1)
        self.assertEqual(source.count('(_("Enigma2 Runtime Health"), "runtimehealth")'), 1)


class NetworkHealthTests(unittest.TestCase):
    def test_network_health_is_bounded_and_read_only(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("def network_health_information")
        end = source.index("def network_diagnostics", start)
        body = source[start:end]
        self.assertIn("/sys/class/net", body)
        self.assertIn("_default_gateway()", body)
        self.assertIn('["ping", "-c", "1", "-W", "2", gateway]', body)
        self.assertIn("/etc/resolv.conf", body)
        self.assertNotIn("ifconfig", body)
        self.assertNotIn("ip addr add", body)

    def test_network_health_menu_wiring(self):
        source = open(PLUGIN, encoding="utf-8").read()
        self.assertEqual(source.count('(_("Network Health"), "nethealth")'), 1)
        self.assertEqual(source.count('"nethealth": (_("Network Health"), network_health_information)'), 1)


class ChannelTechnicalDataTests(unittest.TestCase):
    def test_channel_dashboard_uses_live_enigma2_service_contract(self):
        source = open(PLUGIN, encoding="utf-8").read()
        for token in ("current_service_technical_information", "frontendInfo()", "getAll(True)",
                      "sProvider", "sServiceref", "sVideoPID", "sAudioPID", "sPCRPID",
                      "sPMTPID", "sCAIDs", "channel_technical_summary"):
            self.assertIn(token, source)

    def test_channel_probe_is_read_only(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("def current_service_technical_information")
        end = source.index("def channel_technical_summary", start)
        body = source[start:end]
        for forbidden in ("os.system(", "subprocess.", "killall", "write(", "setFrontend"):
            self.assertNotIn(forbidden, body)


class OriginalGSURestorationTests(unittest.TestCase):
    def test_original_dashboards_and_cam_manager_exist(self):
        source = open(PLUGIN, encoding="utf-8").read()
        for cls in ("GSUSystemDashboard", "GSUChannelDashboard", "GSUActiveCAM", "GSUWarderTools"):
            self.assertIn("class %s" % cls, source)
        self.assertIn('self.setTitle(_("CAM/SRV Manager"))', source)
        self.assertIn('"service_context"', source)
        self.assertIn('"ecm_context"', source)
        self.assertIn("cam_srv_context_information", source)
        self.assertIn("Available CAIDs", source)
        self.assertIn("orbital_position", source)

    def test_original_top_level_routes_to_rich_dashboards(self):
        source = open(PLUGIN, encoding="utf-8").read()
        self.assertIn('self.session.open(GSUSystemDashboard)', source)
        self.assertIn('self.session.open(GSUChannelDashboard)', source)
        self.assertIn('self.session.open(GSUActiveCAM)', source)
        self.assertIn('self.session.open(GSUWarderTools)', source)



class MainMenuFocusTests(unittest.TestCase):
    def test_main_menu_stays_bounded_and_operational(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("class SysUtilMngMain")
        end = source.index("    def __init__", start)
        menu = source[start:end]
        entries = re.findall(r'^\s*\(".*?",\s*".*?"\),\s*$', menu, re.M)
        self.assertLessEqual(len(entries), 20)
        for label in ("System Information", "Channel Information", "OSCam Information",
                      "CAM/SRV Manager", "ECM Information", "Device Manager",
                      "Warder Diagnostics & Tools", "Check for updates"):
            self.assertIn(label, menu)

    def test_low_value_raw_duplicates_are_not_top_level(self):
        source = open(PLUGIN, encoding="utf-8").read()
        start = source.index("class SysUtilMngMain")
        end = source.index("    def __init__", start)
        menu = source[start:end]
        for label in ("Hardware Identity", "Filesystem Health", "Block Devices",
                      "Listening Ports", "CAM Inventory", "Package information",
                      "Image & Runtime", "Diagnostic Summary", "Detected Capabilities",
                      "Health Check", "Service Dashboard", "Network Health",
                      "Network Mount Doctor", "Storage Health", "Enigma2 Runtime Health"):
            self.assertNotIn('("' + label + '",', menu)


class LocalizationContractTests(unittest.TestCase):
    def test_localization_follows_enigma2_language(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        init_py = open(os.path.join(root, "src", "GlassSysUtil", "__init__.py"), encoding="utf-8").read()
        self.assertIn("language.getLanguage()", init_py)
        self.assertIn("gettext.translation", init_py)
        self.assertIn("language.addCallback(localeInit)", init_py)
        self.assertIn("_translation.gettext(text)", init_py)

    def test_menu_labels_use_gettext(self):
        source = open(PLUGIN, encoding="utf-8").read()
        for label in ("System Information", "Channel Information", "OSCam Information",
                      "CAM/SRV Manager", "ECM Information", "Device Manager",
                      "Warder Diagnostics & Tools", "Health Check", "Network Health",
                      "Storage Health", "Check for updates", "Restart Enigma2 GUI", "About this build"):
            self.assertIn('_("' + label + '")', source)

    def test_runtime_titles_and_dialogs_are_localizable(self):
        source = open(PLUGIN, encoding="utf-8").read()
        for text in ("Glass System Utility - Warder Evolution",
                     "CAM/SRV Manager",
                     "System Information",
                     "Channel Information",
                     "Unable to check for updates.\\n\\n%s",
                     "Update installation failed.\\n\\n%s",
                     "Diagnostic bundle created:\\n%s",
                     "About"):
            self.assertIn('_("' + text + '")', source)

    def test_build_compiles_gettext_catalogs(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        build = open(os.path.join(root, "tools", "build-ipk.sh"), encoding="utf-8").read()
        self.assertIn("msgfmt", build)
        self.assertIn("GlassSysUtil.po", build)
        self.assertIn(".mo", build)

    def test_core_languages_are_present(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        for lang in ("sk", "cs", "de", "pl", "it", "es", "fr"):
            path = os.path.join(root, "src", "GlassSysUtil", "locale", lang,
                                "LC_MESSAGES", "GlassSysUtil.po")
            self.assertTrue(os.path.isfile(path), path)
            data = open(path, encoding="utf-8").read()
            self.assertIn('msgid "Health Check"', data)
            self.assertIn('msgid "Check for updates"', data)


if __name__ == "__main__":
    unittest.main()
