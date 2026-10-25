"""Validate the authenticated bridge from the VM without printing its token."""
import json
from pathlib import Path
import subprocess
import urllib.request
import time
root = Path(__file__).resolve().parents[2]
token = (root / '.state/bridge.token').read_text().strip()
for attempt in range(10):
    try:
        req = urllib.request.Request('http://127.0.0.1:18765/health', headers={'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(req, timeout=3) as r: assert json.load(r)['status'] == 'ok'
        break
    except Exception:
        if attempt == 9: raise
        time.sleep(0.5)
# Send HTTP through stdin, never a token-bearing argv or logged command.
script = '''import sys,json,urllib.request
value=sys.stdin.readline().strip()
r=urllib.request.Request('http://127.0.0.1:18766/health',headers={'Authorization':'Bearer '+value})
with urllib.request.urlopen(r,timeout=5) as reply: assert json.load(reply)['status']=='ok'
print('VM tunnel authenticated')
'''
# VM has Python installed by Colima; -c is fixed source, secret only in stdin.
subprocess.run(['colima', '-p', 'pentagi-secure', 'ssh', '--', 'python3', '-c', script], input=token+'\n', text=True, check=True)
