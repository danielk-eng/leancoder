#!/usr/bin/env bash
# Start the Bifrost gateway (npx binary) on 127.0.0.1:8089 using provider keys from .env.
# All caches/tmp stay inside the project.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./.env.sh
set -a; [ -f .env ] && . ./.env; [ -f ../.env ] && . ../.env; set +a
.venv/bin/python scripts/gen_bifrost_config.py
exec npx -y @maximhq/bifrost -app-dir ./bifrost_data -port "${BIFROST_PORT:-8089}" -log-style pretty
