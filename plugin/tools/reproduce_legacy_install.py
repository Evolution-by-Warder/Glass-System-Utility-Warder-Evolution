#!/usr/bin/env python3
"""Run real opkg against isolated roots and guarded legacy 13.20 hooks.

Uses the original postinst and file inventory, minimal old file contents, and
the complete new IPK payload. Receiver paths and script hashes are adjusted
only in disposable fixture copies. No receiver or host package database is used.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile

from build_ipk import archive

ROOT = Path(__file__).resolve().parents[1]
LEGACY = 'enigma2-plugin-glasssysutil'
CURRENT = 'enigma2-plugin-extensions-gsu-warder-evolution'


def read_ipk(path):
    data=Path(path).read_bytes();position=8;result={}
    assert data.startswith(b'!<arch>\n')
    while position < len(data):
        header=data[position:position+60];size=int(header[48:58])
        name=header[:16].decode().strip().rstrip('/')
        result[name]=data[position+60:position+60+size]
        position+=60+size+size%2
    return result


def unpack(data):
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
        return {m.name.lstrip('./'):(tar.extractfile(m).read(),m.mode) for m in tar if m.isfile()}


def package(path, control, files):
    members=[('debian-binary',b'2.0\n'),
             ('control.tar.gz',archive([(name,data,mode) for name,(data,mode) in control.items()])),
             ('data.tar.gz',archive([(name,data,mode) for name,(data,mode) in files.items()]))]
    data=bytearray(b'!<arch>\n')
    for name,body in members:
        data.extend(('%-16s%-12s%-6s%-6s%-8s%-10s`\n'%(name+'/',0,0,0,'100644',len(body))).encode())
        data.extend(body)
        if len(body)%2:data.extend(b'\n')
    path.write_bytes(data)


def guarded(source, root):
    source=re.sub(r"/(?:etc|usr|var|tmp)(?=/|[\s\"';]|$)",lambda m:str(root)+m[0],source)
    source=source.replace(str(root)+'/usr/bin/python3','/usr/bin/python3')
    source=source.replace('-v path="$path"','-v path="${path#${PKG_ROOT%/}}"')
    return ('#!/bin/sh\ncase "$PKG_ROOT" in '+shlex.quote(str(root))+'|'+
            shlex.quote(str(root)+'/')+') ;; *) exit 73 ;; esac\n'+source)


def run_case(opkg, new_ipk, old, parent, fixed):
    root=parent/('fixed' if fixed else 'before');root.mkdir()
    (root/'tmp').mkdir();(root/'etc/enigma2').mkdir(parents=True)
    settings=root/'etc/enigma2/settings';settings.write_text('custom=preserve\n')
    (root/'etc/remote_servers.cfg').write_text('custom-server=preserve\n')
    config=root/'opkg.conf';config.write_text('dest root /\narch all 100\noption check_signature 0\n')
    command=[str(opkg),'-o',str(root),'-f',str(config),'-t',str(root/'tmp'),'--force-postinstall']
    env=dict(os.environ,D='')
    old_hook=guarded(old['postinst'],root)
    old_files={name:(b'legacy fixture\n',0o644) for name in old['data_files']}
    old_files['usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil/version']=(b'13.20\n',0o644)
    first=root/'old.ipk'
    package(first,{'control':(old['control'].encode(),0o644),'postinst':(old_hook.encode(),0o755)},old_files)
    def call(*args):
        return subprocess.run(command+list(args),env=env,text=True,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,timeout=60)
    installed=call('install',str(first))
    assert installed.returncode==0,installed.stdout
    # The original postinst deleted this data, but the opkg list retains it.
    assert not (root/'etc/nfs_cifs-def.cfg').exists()
    assert '/etc/nfs_cifs-def.cfg' in (root/'var/lib/opkg/info'/str(LEGACY+'.list')).read_text()
    sections=read_ipk(new_ipk);control=unpack(sections['control.tar.gz']);files=unpack(sections['data.tar.gz'])
    metadata=control['control'][0].decode()
    metadata='\n'.join(line for line in metadata.splitlines() if not line.startswith('Depends:'))+'\n'
    version=next(line.split(': ',1)[1] for line in metadata.splitlines() if line.startswith('Version: '))
    control['control']=(metadata.encode(),0o644)
    for name in ('preinst','postinst','prerm'):
        if name in control:
            source=control[name][0].decode()
            if name=='preinst':
                source=source.replace(old['postinst_sha256'],hashlib.sha256(old_hook.encode()).hexdigest())
                if not fixed:source='#!/bin/sh\nexit 0\n'
            control[name]=(guarded(source,root).encode(),0o755)
    second=root/'new.ipk';package(second,control,files)
    result=call('install',str(second))
    status=call('status',CURRENT)
    errors=result.stdout.count('error: remove_obsolesced_files:')
    (parent/('fixed.log' if fixed else 'before.log')).write_text(result.stdout)
    assert result.returncode==0,result.stdout
    assert 'Version: '+version in status.stdout and 'Status: install ok installed' in status.stdout,status.stdout
    assert settings.read_text()=='custom=preserve\n'
    assert (root/'etc/remote_servers.cfg').read_text()=='custom-server=preserve\n'
    for name,(data,mode) in files.items():
        assert (root/name).read_bytes()==data,name
    if fixed:assert errors==0,result.stdout
    else:assert errors>0,'Original missing-file failure was not reproduced'
    return {'preparation_enabled':fixed,'opkg_exit':result.returncode,
            'obsolete_file_errors':errors,'final_package_installed':True,
            'all_new_payload_bytes_match':True,'settings_preserved':True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--opkg',type=Path,required=True)
    parser.add_argument('--ipk',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    old=json.loads((ROOT/'tests/fixtures/legacy_gsu_13_20.json').read_text())
    assert hashlib.sha256(old['postinst'].encode()).hexdigest()==old['postinst_sha256']
    with tempfile.TemporaryDirectory(prefix='warder-gsu-opkg-') as temp:
        parent=Path(temp)
        report={'original_ipk_sha256':old['original_ipk_sha256'],
                'opkg_version':subprocess.check_output([str(args.opkg),'--version'],text=True).strip(),
                'before':run_case(args.opkg,args.ipk,old,parent,False),
                'fixed':run_case(args.opkg,args.ipk,old,parent,True),
                'limits':'Isolated host test: original legacy hook/inventory with minimal old file contents, complete new payload; not a receiver test.'}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
