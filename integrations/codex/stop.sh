#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
DOCKER_CONTEXT=colima-pentagi-secure docker-compose --env-file .state/secure.env -f integrations/codex/compose.yml down
python3 integrations/codex/services.py stop
# Data volumes persist. The dedicated VM can be stopped separately:
# colima stop pentagi-secure
