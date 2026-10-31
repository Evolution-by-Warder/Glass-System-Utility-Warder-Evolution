import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/GlassSysUtil'))
sys.path.insert(0,str(ROOT/'tools'))
import plugin_update as update
import build_ipk
import publish_update

spec=importlib.util.spec_from_file_location('gsu_r92_updater',Path(__file__).parent/'fixtures/plugin_update_r92.py')
old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)


class PackageIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory()
        root=Path(cls.folder.name)
        cls.bridge=build_ipk.build(root/'bridge',bridge=True)
        cls.current=build_ipk.build(root/'current')
        cls.bridge_doc=publish_update.manifest(cls.bridge,'13.40-r93','Compatible transition')
        short=cls.current.with_name('enigma2-plugin-extensions-gsu_13.40-r94_all.ipk')
        cls.current_doc=publish_update.manifest(short,'13.40-r94','Correct plugin group')
        cls.release=update.parse_release(json.dumps(cls.current_doc),'13.40-r93')

    @classmethod
    def tearDownClass(cls):cls.folder.cleanup()

    def test_only_short_filename_is_built_with_unchanged_package_identity(self):
        self.assertEqual(self.current.name,'enigma2-plugin-extensions-gsu_13.40-r94_all.ipk')
        self.assertEqual(list(self.current.parent.glob('*.ipk')),[self.current])
        update.validate_ipk(self.current,self.release)

    def test_original_r92_accepts_actual_bridge_bytes_and_rejects_new_identity(self):
        offered=old.parse_release(json.dumps(self.bridge_doc),'13.40-r92')
        old.validate_ipk(self.bridge,offered)
        with self.assertRaises(old.UpdateError):old.parse_release(json.dumps(self.current_doc),'13.40-r92')

    def test_bridge_updater_accepts_new_identity_and_same_native_runtime_directory(self):
        update.validate_ipk(self.current,self.release)
        self.assertEqual(self.release.package_id,'enigma2-plugin-extensions-gsu-warder-evolution')
        self.assertEqual(update.FEED_URL.rsplit('/',1)[-1],'stable.json')
        self.assertEqual(self.current_doc['release']['sha256'],hashlib.sha256(self.current.read_bytes()).hexdigest())

    def install(self,legacy_version,returncode=0):
        data=self.current.read_bytes();calls=[]
        def opener(url,**kwargs):
            if url.endswith('candidate.json'):return io.BytesIO(json.dumps(self.bridge_doc).encode())
            if url==self.bridge_doc['release']['url']:return io.BytesIO(self.bridge.read_bytes())
            return io.BytesIO(data)
        with tempfile.TemporaryDirectory() as folder:
            flag=Path(folder)/'state/rename'
            def runner(command,**kwargs):
                calls.append(command[:2])
                if command[1]=='status':
                    identity=command[2]
                    version=legacy_version if identity==update.LEGACY_PACKAGE_ID else '13.40-r94'
                    return types.SimpleNamespace(returncode=0,stdout='Package: '+identity+'\nVersion: '+version+'\nStatus: install ok installed\n')
                self.assertTrue(flag.is_file())
                self.assertEqual(flag.read_text(),'13.40-r94\n')
                return types.SimpleNamespace(returncode=returncode,stdout='opkg result')
            with patch.object(update,'MIGRATION_FLAG',flag), patch.object(update,'verify_installation'):
                if returncode or legacy_version=='13.40-r92':
                    with self.assertRaises(update.UpdateError):update.install_release(self.release,opener,runner)
                else:self.assertEqual(update.install_release(self.release,opener,runner),'13.40-r94')
            self.assertFalse(flag.exists())
        return calls

    def test_rename_preserves_cam_settings_during_opkg_and_removes_temporary_marker(self):
        self.assertEqual(self.install('13.40-r93'),[['opkg','status'],['opkg','remove'],['opkg','install']])

    def test_marker_is_removed_when_opkg_reports_failure(self):
        self.install('13.40-r93',1)

    def test_installed_pre_bridge_cannot_be_renamed_directly(self):
        self.assertEqual(self.install('13.40-r92'),[['opkg','status']])

    def test_failed_new_install_restores_verified_legacy_package_before_clearing_marker(self):
        calls=[]
        with tempfile.TemporaryDirectory() as folder:
            flag=Path(folder)/'state/rename'
            def opener(url,**kwargs):
                if url.endswith('candidate.json'):return io.BytesIO(json.dumps(self.bridge_doc).encode())
                return io.BytesIO(self.bridge.read_bytes() if url==self.bridge_doc['release']['url'] else self.current.read_bytes())
            def runner(command,**kwargs):
                calls.append(command[:2])
                if command[1]=='status':return types.SimpleNamespace(returncode=0,stdout='Package: '+update.LEGACY_PACKAGE_ID+'\nVersion: 13.40-r93\nStatus: install ok installed\n')
                self.assertTrue(flag.is_file())
                failed=command[1]=='install' and command[2].endswith('update.ipk')
                return types.SimpleNamespace(returncode=1 if failed else 0,stdout='fixture')
            with patch.object(update,'MIGRATION_FLAG',flag),self.assertRaisesRegex(update.UpdateError,'previous GSU was restored'):
                update.install_release(self.release,opener,runner)
            self.assertFalse(flag.exists())
        self.assertEqual(calls,[['opkg','status'],['opkg','remove'],['opkg','install'],['opkg','remove'],['opkg','install']])
