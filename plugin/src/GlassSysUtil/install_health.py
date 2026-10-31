"""Verify payload hashes and final opkg state without importing Enigma2."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

PACKAGE = 'enigma2-plugin-extensions-gsu-warder-evolution'
LEGACY_PACKAGE = 'enigma2-plugin-glasssysutil'


def verify_files(expected_version=None, runtime=None):
    runtime = Path(runtime) if runtime is not None else Path(__file__).parent
    manifest = json.loads((runtime / 'installed-files.json').read_text())
    version = (runtime / 'version').read_text().strip()
    if (not version or version != manifest.get('version') or
            (expected_version is not None and version != expected_version)):
        raise ValueError('Installed GSU version does not match the requested release')
    files = manifest.get('files', {})
    required = {'plugin.py', 'plugin_update.py', 'install_health.py',
                'warder_main.py', 'native_start_config.py', 'i18n.py', 'version'}
    if not required.issubset(files):
        raise ValueError('Incomplete GSU installation manifest')
    for name, digest in files.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid installed GSU file path')
        path = runtime / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Incomplete GSU installation: missing ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Installed GSU file is damaged: ' + name)
    return version


def verify_installation(expected_version, package=PACKAGE, runner=subprocess.run, runtime=None):
    version = verify_files(expected_version, runtime)
    if package not in (PACKAGE, LEGACY_PACKAGE):
        raise ValueError('Unexpected installed GSU package identity')
    result = runner(['opkg', 'status', package], stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, timeout=15)
    if result.returncode == 0:
        for paragraph in result.stdout.split('\n\n'):
            fields = dict(line.split(': ', 1) for line in paragraph.splitlines()
                          if ': ' in line and not line[:1].isspace())
            if (fields.get('Package') == package and fields.get('Version') == version and
                    fields.get('Status', '').split() == ['install', 'ok', 'installed']):
                return version
    raise ValueError('GSU package is not completely installed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--files-only', action='store_true')
    parser.add_argument('--expected-version')
    parser.add_argument('--package', default=PACKAGE)
    args = parser.parse_args()
    try:
        if args.files_only:
            verify_files(args.expected_version)
        else:
            verify_installation(args.expected_version, args.package)
    except (OSError, ValueError, TypeError) as error:
        print('GSU installation verification failed: ' + str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
