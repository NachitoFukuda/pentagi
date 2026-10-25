#!/usr/bin/env python3
"""Run this project's CLI bridge and tunnel under the macOS user service manager.

Plists stay inside private .state, not ~/Library/LaunchAgents: no login/boot setup.
No credential values are placed in a plist, environment, or process argument.
"""
import argparse
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / '.state'
DOMAIN = 'gui/' + str(os.getuid())
PREFIX = 'app.pentagi.codex.' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]


def job_definitions(model, executable):
    environment = {k: os.environ[k] for k in ('HOME', 'PATH', 'TMPDIR', 'LANG', 'USER', 'LOGNAME',
                                              'CODEX_HOME', 'SSL_CERT_FILE', 'SSL_CERT_DIR') if k in os.environ}
    environment['PENTAGI_BRIDGE_REVISION'] = hashlib.sha256((ROOT / 'integrations/codex/bridge.py').read_bytes()).hexdigest()
    common = {'WorkingDirectory': str(ROOT), 'EnvironmentVariables': environment,
              'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 5,
              'ProcessType': 'Background', 'Umask': 0o077}
    programs = {
        'bridge': [str(Path(sys.executable).resolve()), '-u', str(ROOT / 'integrations/codex/bridge.py'),
                   '--token-file', str(STATE / 'bridge.token'), '--model', model, '--codex', executable],
        'tunnel': ['/usr/bin/ssh', '-F', str(Path.home() / '.colima/_lima/colima-pentagi-secure/ssh.config'),
                   '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'ExitOnForwardFailure=yes',
                   '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3', '-N',
                   '-R', '127.0.0.1:18766:127.0.0.1:18765', 'lima-colima-pentagi-secure'],
    }
    return {name: dict(common, Label=PREFIX + '.' + name, ProgramArguments=args,
                       StandardOutPath=str(STATE / (name + '.log')),
                       StandardErrorPath=str(STATE / (name + '.log'))) for name, args in programs.items()}


def loaded(label):
    return subprocess.run(['/bin/launchctl', 'print', DOMAIN + '/' + label],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def stop_legacy(name):
    path = STATE / (name + '.pid')
    if not path.exists():
        return
    pid = path.read_text().strip()
    if not pid.isdigit():
        raise SystemExit('Invalid legacy PID file: ' + name)
    process = subprocess.run(['/bin/ps', '-p', pid, '-o', 'args='], capture_output=True, text=True)
    expected = ('integrations/codex/bridge.py' in process.stdout if name == 'bridge' else
                '127.0.0.1:18765:127.0.0.1:18765' in process.stdout and 'lima-colima-pentagi-secure' in process.stdout)
    if process.returncode == 0:
        if not expected:
            raise SystemExit('Refusing to stop an unrelated process from stale ' + name + '.pid')
        os.kill(int(pid), signal.SIGTERM)
        time.sleep(0.2)
    path.unlink()


def stop():
    for name in ('tunnel', 'bridge'):
        label = PREFIX + '.' + name
        if loaded(label):
            subprocess.run(['/bin/launchctl', 'bootout', DOMAIN + '/' + label], check=True)
        stop_legacy(name)
    print('Project CLI services stopped; no login/boot service remains installed.')


def start(model, executable):
    directory = STATE / 'launchd'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    definitions = job_definitions(model, executable)
    load_job('bridge', definitions['bridge'], directory)
    wait_bridge()
    load_job('tunnel', definitions['tunnel'], directory)


def load_job(name, definition, directory):
    stop_legacy(name)
    label = definition['Label']
    path = directory / (name + '.plist')
    content = plistlib.dumps(definition)
    same = path.exists() and path.read_bytes() == content
    if loaded(label) and same:
        print(name + ' service already loaded')
        return
    if loaded(label):
        subprocess.run(['/bin/launchctl', 'bootout', DOMAIN + '/' + label], check=True)
    path.write_bytes(content)
    path.chmod(0o600)
    subprocess.run(['/bin/launchctl', 'bootstrap', DOMAIN, str(path)], check=True)
    print(name + ' service loaded')


def wait_bridge():
    token = (STATE / 'bridge.token').read_text().strip()
    request = urllib.request.Request('http://127.0.0.1:18765/health', headers={'Authorization': 'Bearer ' + token})
    for attempt in range(30):
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    print('Codex CLI bridge ready (ChatGPT login).')
                    return
        except OSError:
            time.sleep(0.5)
    raise SystemExit('CLI bridge did not become ready; inspect private .state/bridge.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--model', default=os.environ.get('PENTAGI_CODEX_MODEL', 'gpt-6.1-sol'))
    parser.add_argument('--codex', default=shutil.which('codex'))
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This service manager is for the isolated macOS setup')
    if args.action == 'stop':
        return stop()
    if not args.codex or not Path(args.codex).is_absolute() or not Path(args.codex).is_file():
        parser.error('A full path to the official Codex CLI is required')
    start(args.model, args.codex)


if __name__ == '__main__':
    main()
