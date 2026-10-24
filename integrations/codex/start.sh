#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
STATE="$ROOT/.state"
CONTEXT=colima-pentagi-secure
MODEL=${PENTAGI_CODEX_MODEL:-gpt-6.1-sol}
mkdir -p "$STATE"
chmod 700 "$STATE"
# A separate VM, no home/filesystem mounts and no forwarded SSH agent.
colima start pentagi-secure --cpu 2 --memory 3 --disk 24 --mount none --ssh-agent=false --ssh-config=false --activate=false --template=false
if ! docker --context "$CONTEXT" network inspect pentagi-workers >/dev/null 2>&1; then
  docker --context "$CONTEXT" network create --internal --driver bridge --opt com.docker.network.bridge.name=br-pentagiwork pentagi-workers >/dev/null
fi
colima -p pentagi-secure ssh -- sh -s < integrations/codex/isolate.sh
python3 integrations/codex/setup.py
# Process ownership lives in private pid files, not a machine-wide service.
if [ -f "$STATE/bridge.pid" ] && kill -0 "$(cat "$STATE/bridge.pid")" 2>/dev/null; then
  echo "Bridge is already running"
else
  nohup python3 -u integrations/codex/bridge.py --token-file "$STATE/bridge.token" --model "$MODEL" > "$STATE/bridge.log" 2>&1 < /dev/null &
  echo $! > "$STATE/bridge.pid"
fi
if [ -f "$STATE/tunnel.pid" ] && kill -0 "$(cat "$STATE/tunnel.pid")" 2>/dev/null; then
  echo "Tunnel is already running"
else
  nohup ssh -F "$HOME/.colima/_lima/colima-pentagi-secure/ssh.config" -o ControlMaster=no -o ControlPath=none -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -N -R 127.0.0.1:18765:127.0.0.1:18765 lima-colima-pentagi-secure > "$STATE/tunnel.log" 2>&1 < /dev/null &
  echo $! > "$STATE/tunnel.pid"
fi
# Check authenticated bridge over the tunnel before starting the app.
python3 integrations/codex/check_tunnel.py
# Never runs docker compose against the user's current/default context.
DOCKER_CONTEXT="$CONTEXT" docker-compose --env-file "$STATE/secure.env" -f integrations/codex/compose.yml up -d
printf '%s\n' 'PentAGI: http://127.0.0.1:18443' 'Credentials: .state/login.txt'
