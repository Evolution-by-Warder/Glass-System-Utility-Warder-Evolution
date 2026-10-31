#!/usr/bin/env python3
"""Inspect every source module in the real new IPK and exercise its verifier."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

from reproduce_legacy_install import read_ipk,unpack

ROOT=Path(__file__).resolve().parents[1]
VERSION='13.40-r95'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil/'


def main():
    path=ROOT/'build'/('enigma2-plugin-extensions-gsu_'+VERSION+'_all.ipk')
    sections=read_ipk(path);control=unpack(sections['control.tar.gz']);payload=unpack(sections['data.tar.gz'])
    assert 'Package: enigma2-plugin-extensions-gsu-warder-evolution\n' in control['control'][0].decode()
    assert ('Version: '+VERSION+'\n').encode() in control['control'][0]
    assert control['preinst'][0]==(ROOT/'control/preinst').read_bytes()
    assert b'--files-only' in control['postinst'][0]
    for module in (ROOT/'src/GlassSysUtil').glob('*.py'):
        assert payload[PREFIX+module.name][0]==module.read_bytes(),module.name
    assert not any('__pycache__' in name or name.endswith(('.pyc','.pyo')) for name in payload)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for name,(data,mode) in payload.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        runtime=root/PREFIX
        spec=importlib.util.spec_from_file_location('gsu_packaged_health',runtime/'install_health.py')
        health=importlib.util.module_from_spec(spec);spec.loader.exec_module(health)
        status=lambda *a,**k:SimpleNamespace(returncode=0,stdout='Package: '+health.PACKAGE+'\nVersion: '+VERSION+'\nStatus: install ok installed\n')
        assert health.verify_installation(VERSION,runner=status,runtime=runtime)==VERSION
        for key in ('plugin.py','plugin_update.py','version'):
            p=runtime/key;before=p.read_bytes();p.write_bytes(b'broken')
            try:health.verify_installation(VERSION,runner=status,runtime=runtime)
            except (ValueError,OSError):pass
            else:raise AssertionError('Incomplete payload accepted: '+key)
            p.write_bytes(before)
        spec=importlib.util.spec_from_file_location('gsu_packaged_history',runtime/'release_history.py')
        history=importlib.util.module_from_spec(spec);spec.loader.exec_module(history)
        for language in ('sk','cs','en','de','pl','hu','ru','fr','it','es'):
            rendered=history.load_notes(runtime/'release-history.json',VERSION,language)
            assert rendered.count('GSU ')==4 and rendered.count('────────────────────────')==3
    isolation=json.loads((ROOT/'build/feed-isolation.json').read_text())
    assert isolation=={name:hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest() for name in isolation}
    report={'version':VERSION,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'all_source_modules_match':True,'packaged_payload_health_tested':True,
            'four_history_entries_in_ten_languages':True,'stable_feeds_unchanged':True,'receiver_test':False}
    (ROOT/'build/verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
