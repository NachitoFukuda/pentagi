#!/usr/bin/env python3
"""Generate local secrets and a minimal runtime build context; never copies CLI auth."""
from pathlib import Path
import argparse
import os
import secrets
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / '.state'
CONTEXT = 'colima-pentagi-secure'


def main():
    STATE.mkdir(exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    token_path = STATE / 'bridge.token'
    if not token_path.exists(): token_path.write_text(secrets.token_urlsafe(48) + '\n')
    token_path.chmod(0o600)
    env_path = STATE / 'secure.env'
    if not env_path.exists():
        gid = subprocess.check_output(['colima', '-p', 'pentagi-secure', 'ssh', '--',
                                       'sudo', 'stat', '-c', '%g', '/var/run/docker.sock'], text=True).strip()
        if not gid.isdigit(): raise SystemExit('Cannot determine isolated Docker socket group')
        values = {'DATABASE_PASSWORD': secrets.token_urlsafe(36),
                  'COOKIE_SIGNING_SALT': secrets.token_urlsafe(48),
                  'ADMIN_PASSWORD': secrets.token_urlsafe(24),
                  'BRIDGE_TOKEN': token_path.read_text().strip(), 'DOCKER_SOCKET_GID': gid}
        env_path.write_text(''.join(k + '=' + v + '\n' for k, v in values.items()))
        (STATE / 'login.txt').write_text('URL: http://127.0.0.1:18443\nUser: admin@pentagi.com\nPassword: ' + values['ADMIN_PASSWORD'] + '\n')
        (STATE / 'login.txt').chmod(0o600)
    env_path.chmod(0o600)
    build = STATE / 'runtime-context'
    build.mkdir(exist_ok=True)
    binary = STATE / 'pentagi-linux-arm64'
    assets = ROOT / 'frontend/dist'
    if not binary.exists() or not (assets / 'index.html').exists():
        raise SystemExit('Build the Linux ARM64 backend and frontend first')
    shutil.copy2(binary, build / 'pentagi')
    shutil.copytree(assets, build / 'fe', dirs_exist_ok=True)
    shutil.copy2(Path(__file__).with_name('Dockerfile.runtime'), build / 'Dockerfile')
    subprocess.run(['docker', '--context', CONTEXT, 'build', '--network=none',
                    '-t', 'pentagi-codex:local', str(build)], check=True)
    print('Runtime built. Local credentials are in .state/login.txt (private).')


if __name__ == '__main__': main()
