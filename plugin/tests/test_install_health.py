import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/GlassSysUtil'))
sys.path.insert(0, str(ROOT/'tools'))
import build_ipk
import install_health as health
import plugin_update as update


class HealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.package = build_ipk.build(Path(cls.temp.name)/'build')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        raw = self.package.read_bytes(); pos = 8
        while pos < len(raw):
            h = raw[pos:pos+60]; n = int(h[48:58]); name = h[:16].decode().strip().rstrip('/')
            data = raw[pos+60:pos+60+n]; pos += 60+n+n%2
            if name == 'data.tar.gz':
                with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
                    for m in tar:
                        if m.isfile():
                            relative = Path(m.name.lstrip('./'))
                            p = self.root/relative;p.parent.mkdir(parents=True,exist_ok=True)
                            p.write_bytes(tar.extractfile(m).read())
        self.runtime = self.root/build_ipk.PLUGIN
        self.version = (self.runtime/'version').read_text().strip()

    def status(self, status='install ok installed', version=None, package=None):
        return lambda *a, **k: SimpleNamespace(returncode=0, stdout='Package: %s\nVersion: %s\nStatus: %s\n' % (
            package or health.PACKAGE, version or self.version, status))

    def test_actual_built_payload_passes_and_every_core_module_has_a_hash(self):
        self.assertEqual(health.verify_installation(self.version, runner=self.status(), runtime=self.runtime), self.version)
        manifest = json.loads((self.runtime/'installed-files.json').read_text())
        self.assertTrue({p.name for p in self.runtime.glob('*.py')}.issubset(manifest['files']))

    def test_missing_or_corrupt_core_file_cannot_be_success(self):
        p = self.runtime/'plugin.py';original = p.read_bytes()
        for value in (b'', b'# damaged\n', None):
            if p.exists():p.unlink()
            if value is not None:p.write_bytes(value)
            with self.subTest(value=value), self.assertRaises((ValueError,OSError)):
                health.verify_installation(self.version, runner=self.status(), runtime=self.runtime)
        p.write_bytes(original)

    def test_wrong_version_identity_and_unpacked_status_are_rejected(self):
        for state,version,package in [('install ok unpacked',None,None),('deinstall ok installed',None,None),
                                      ('install ok installed','13.40-r0',None),('install ok installed',None,'other')]:
            with self.subTest(state=state,version=version,package=package), self.assertRaises(ValueError):
                health.verify_installation(self.version, runner=self.status(state,version,package),runtime=self.runtime)

    def test_updater_rejects_failed_final_helper_even_after_opkg_zero(self):
        calls=[]
        def runner(command, **kwargs):
            calls.append(command)
            if command[:2]==['opkg','status']:return SimpleNamespace(returncode=1,stdout='')
            if command[:2]==['opkg','install']:return SimpleNamespace(returncode=0,stdout='configured')
            return SimpleNamespace(returncode=1,stdout='missing plugin.py')
        release=SimpleNamespace(version=self.version,package_id=update.PACKAGE_ID)
        with patch.object(update,'download_release',return_value=self.package),patch.object(update,'validate_ipk'):
            with self.assertRaisesRegex(update.UpdateError,'verification failed'):
                update.install_release(release,runner=runner)
        self.assertTrue(any(command[:2]==['opkg','install'] for command in calls))
        self.assertEqual(calls[-1][0],'/usr/bin/python3')


class LegacyPreinstTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.info=self.root/'var/lib/opkg/info';self.info.mkdir(parents=True)
        self.fixture=json.loads((ROOT/'tests/fixtures/legacy_gsu_13_20.json').read_text())
        self.old=self.info/'enigma2-plugin-glasssysutil'
        Path(str(self.old)+'.postinst').write_text(self.fixture['postinst'])
        self.paths=self.fixture['self_deleted_paths']
        for path in self.paths:(self.root/path.lstrip('/')).parent.mkdir(parents=True,exist_ok=True)
        Path(str(self.old)+'.list').write_text(''.join(str(self.root/p.lstrip('/'))+'\t0100644\n' for p in self.paths))
        self.script=re.sub(r'/(?:etc|usr|var|tmp)/',lambda m:str(self.root)+m[0],(ROOT/'control/preinst').read_text())

    def run_script(self):
        return subprocess.run(['sh','-c',self.script,'preinst','upgrade','13.20'],text=True,capture_output=True,env={'PATH':'/usr/bin:/bin'})

    def test_exact_self_deleted_tracked_entries_are_prepared(self):
        r=self.run_script();self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        for p in self.paths:self.assertEqual((self.root/p.lstrip('/')).read_bytes(),b'')

    def test_renamed_install_invocation_also_prepares_verified_legacy_files(self):
        r=subprocess.run(['sh','-c',self.script,'preinst','install'],text=True,capture_output=True,env={'PATH':'/usr/bin:/bin'})
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        for p in self.paths:self.assertEqual((self.root/p.lstrip('/')).read_bytes(),b'')

    def test_existing_files_and_symlinks_are_preserved(self):
        p=self.root/self.paths[0].lstrip('/');p.write_bytes(b'keep')
        q=self.root/self.paths[1].lstrip('/');q.symlink_to('absent-user-target')
        self.assertEqual(self.run_script().returncode,0)
        self.assertEqual(p.read_bytes(),b'keep');self.assertTrue(q.is_symlink())

    def test_untracked_and_unknown_paths_are_not_created(self):
        Path(str(self.old)+'.list').write_text('/unknown-file\t0100644\n')
        self.assertEqual(self.run_script().returncode,0)
        self.assertFalse(any((self.root/p.lstrip('/')).exists() for p in self.paths))

    def test_unknown_hooks_abort_before_any_placeholder(self):
        Path(str(self.old)+'.postinst').write_text('#!/bin/sh\nexit 0\n')
        self.assertNotEqual(self.run_script().returncode,0)
        self.assertFalse(any((self.root/p.lstrip('/')).exists() for p in self.paths))

    def test_missing_parent_and_symlinked_list_abort(self):
        self.root.joinpath(self.paths[0].lstrip('/')).parent.rmdir()
        self.assertNotEqual(self.run_script().returncode,0)

    def test_symlinked_ownership_list_is_not_used(self):
        listing=Path(str(self.old)+'.list');listing.rename(self.root/'untrusted-list')
        listing.symlink_to(self.root/'untrusted-list')
        self.assertNotEqual(self.run_script().returncode,0)
        self.assertFalse(any((self.root/p.lstrip('/')).exists() for p in self.paths))


if __name__=='__main__':unittest.main()
