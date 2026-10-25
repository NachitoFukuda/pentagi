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
# User-owned launchd jobs outlive the terminal/chat process. Plists remain in
# private .state, without automatic startup on the next login or machine boot.
python3 integrations/codex/services.py start --model "$MODEL"
# Check authenticated bridge over the tunnel before starting the app.
attempt=0
until python3 integrations/codex/check_tunnel.py; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 10 ] || exit 1
  sleep 1
done
# Never runs docker compose against the user's current/default context.
DOCKER_CONTEXT="$CONTEXT" docker-compose --env-file "$STATE/secure.env" -f integrations/codex/compose.yml up -d
printf '%s\n' 'PentAGI: http://127.0.0.1:18443' 'Credentials: .state/login.txt'
