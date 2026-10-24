#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
DOCKER_CONTEXT=colima-pentagi-secure docker-compose --env-file .state/secure.env -f integrations/codex/compose.yml down
for name in bridge tunnel; do
  if [ -f ".state/$name.pid" ]; then
    kill "$(cat ".state/$name.pid")" 2>/dev/null || true
    rm ".state/$name.pid"
  fi
done
# Data volumes persist. The dedicated VM can be stopped separately:
# colima stop pentagi-secure
