#!/usr/bin/env python3
"""Build the separate original-runtime receiver candidate without old bytecode."""
import argparse
import gzip
import hashlib
import io
import json
import pathlib
import tarfile
from xml.etree import ElementTree

BASE=pathlib.Path(__file__).resolve().parents[1]
PLUGIN='usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil'
PACKAGE='enigma2-plugin-extensions-gsu-warder-evolution'
LEGACY_PACKAGE='enigma2-plugin-glasssysutil'


def archive(entries):
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w',format=tarfile.GNU_FORMAT) as output:
        directories=set()
        for name,data,mode in sorted(entries):
            for parent in reversed(pathlib.PurePosixPath(name).parents):
                if str(parent)=='.' or str(parent) in directories:continue
                info=tarfile.TarInfo('./'+str(parent));info.type=tarfile.DIRTYPE;info.mode=0o755;info.mtime=0
                output.addfile(info);directories.add(str(parent))
            info=tarfile.TarInfo('./'+name);info.size=len(data);info.mode=mode;info.mtime=0
            output.addfile(info,io.BytesIO(data))
    return gzip.compress(raw.getvalue(),mtime=0)


def build(destination, bridge=False):
    runtime=BASE/'src/GlassSysUtil'
    version='13.40-r93' if bridge else (runtime/'version').read_text().strip()
    package=LEGACY_PACKAGE if bridge else PACKAGE
    resources=BASE/'resources.tar.gz'
    manifest=json.loads((BASE/'resources.json').read_text())
    assert hashlib.sha256(resources.read_bytes()).hexdigest()==manifest['archive_sha256']
    entries=[];seen=set()
    with tarfile.open(resources) as tar:
        for member in tar:
            name=pathlib.PurePosixPath(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            assert str(name) not in seen
            raw=tar.extractfile(member).read()
            assert hashlib.sha256(raw).hexdigest()==manifest['files'][str(name)]
            if str(name)=='keymap.xml':
                keymap=ElementTree.fromstring(raw)
                for context in list(keymap):
                    if context.get('context')=='GSUmain':keymap.remove(context)
                raw=ElementTree.tostring(keymap,encoding='utf-8')
            entries.append((PLUGIN+'/'+str(name),raw,0o755 if str(name).startswith('bin/') or str(name).endswith('.sh') else 0o644));seen.add(str(name))
    assert seen==set(manifest['files'])
    for path in sorted(runtime.glob('*.py')):
        compile(path.read_text(),str(path),'exec')
        entries.append((PLUGIN+'/'+path.name,path.read_bytes(),0o644))
    for path in sorted((runtime/'images').glob('*.png')):
        entries.append((PLUGIN+'/images/'+path.name,path.read_bytes(),0o644))
    for path in sorted((runtime/'locale').glob('*.json')):
        entries.append((PLUGIN+'/locale/'+path.name,path.read_bytes(),0o644))
    entries.append((PLUGIN+'/version',(version+'\n').encode(),0o644))
    notes=(BASE/'update/RELEASE-NOTES.md').read_text()
    if bridge:notes=notes.replace('GSU 13.40-r94','GSU 13.40-r93',1)
    assert notes.splitlines()[0]=='GSU '+version,'Release notes do not match runtime version'
    entries.append((PLUGIN+'/release-notes.txt',notes.encode('utf-8'),0o644))
    history=json.loads((BASE/'update/RELEASE-NOTES.i18n.json').read_text())
    history['version']=version
    if bridge:
        history['entries']=[entry for entry in history['entries']
                            if int(entry['version'].rsplit('r',1)[1])<=93]
    entries.append((PLUGIN+'/release-history.json',
                    (json.dumps(history,ensure_ascii=False,indent=2)+'\n').encode(),0o644))
    for path in sorted((BASE/'converters').glob('*.py')):
        compile(path.read_text(),str(path),'exec')
        entries.append(('usr/lib/enigma2/python/Components/Converter/'+path.name,path.read_bytes(),0o644))
    # The old runtime reads these images' conventional configuration locations.
    # Existing receiver configuration and custom scripts are never overwritten.
    for path in sorted((BASE/'defaults').iterdir()):
        entries.append((PLUGIN+'/defaults/'+path.name,path.read_bytes(),0o644))
    control=('Package: '+package+'\nVersion: '+version+'\nArchitecture: all\nSection: '+('extra' if bridge else 'extensions')+'\nPriority: optional\nMaintainer: Warder Evolution\nDepends: enigma2, python3-core, python3-xml, python3-netclient, python3-compression, python3-fcntl, python3-json, python3-threading, ca-certificates\nDescription: GSU Warder Evolution: receiver information, CAM/ECM management and diagnostics\n'+('' if bridge else 'Replaces: '+LEGACY_PACKAGE+'\nConflicts: '+LEGACY_PACKAGE+'\n')).encode()
    checked = {name[len(PLUGIN)+1:]: hashlib.sha256(data).hexdigest()
               for name, data, mode in entries if name.startswith(PLUGIN+'/')
               and (name.endswith('.py') or name == PLUGIN+'/version')}
    entries.append((PLUGIN+'/installed-files.json',
                    (json.dumps({'version':version,'files':checked},sort_keys=True,indent=2)+'\n').encode(),0o644))
    preinst=(BASE/'control/preinst').read_bytes()
    postinst='''#!/bin/sh
set -e
[ -z "$D" ] || exit 0
p=/usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil
rm -rf "$p/__pycache__"
for log in "$p/gsu.log" /tmp/gsu-softcam-autostart.log /tmp/gsu-bitrate.log; do
    if [ -f "$log" ] && [ ! -L "$log" ]; then rm -f "$log"; fi
done
for name in remote_servers nfs_cifs; do
    [ -e "/etc/$name.cfg" ] || cp "$p/defaults/$name-def.cfg" "/etc/$name.cfg"
done
[ -e /etc/piconPaths.conf ] || cp "$p/defaults/piconPaths-def.conf" /etc/piconPaths.conf
[ -e /etc/hddtemp.db ] || cp "$p/defaults/hddtemp-def.db" /etc/hddtemp.db
[ -e /etc/oscam_version ] || cp "$p/defaults/oscam_version" /etc/oscam_version
/usr/bin/python3 "$p/install_health.py" --files-only
printf '%s\\n' 'GSU files verified. Restart the GUI after installation completes.'
exit 0
'''.encode()
    prerm=b"""#!/bin/sh
set -e
[ -z "$D" ] || exit 0
if [ "$1" = remove ] && [ ! -f /var/lib/warder-gsu/package-rename-in-progress ]; then
    helper=/usr/lib/enigma2/python/Plugins/Extensions/GlassSysUtil/native_start_config.py
    if [ -f "$helper" ]; then /usr/bin/python3 "$helper" --restore-all; fi
fi
exit 0
"""
    sections=[('debian-binary',b'2.0\n'),('control.tar.gz',archive([('control',control,0o644),('preinst',preinst,0o755),('postinst',postinst,0o755),('prerm',prerm,0o755)])),('data.tar.gz',archive(entries))]
    result=bytearray(b'!<arch>\n')
    for name,data in sections:
        result.extend(('%-16s%-12s%-6s%-6s%-8s%-10s`\n'%(name+'/',0,0,0,'100644',len(data))).encode());result.extend(data)
        if len(data)%2:result.extend(b'\n')
    destination=pathlib.Path(destination);destination.mkdir(parents=True,exist_ok=True)
    filename_prefix=LEGACY_PACKAGE if bridge else 'enigma2-plugin-extensions-gsu'
    path=destination/(filename_prefix+'_'+version+'_all.ipk');path.write_bytes(result)
    digest=hashlib.sha256(result).hexdigest();path.with_suffix('.ipk.sha256').write_text(digest+'  '+path.name+'\n')
    print(path);print(len(result),'bytes SHA256',digest)
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(BASE/'dist'));parser.add_argument('--bridge',action='store_true');args=parser.parse_args();build(args.output,args.bridge)
