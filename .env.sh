# source me: keeps every cache/tmp inside the project
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TMPDIR="$ROOT/.cache/tmp" npm_config_cache="$ROOT/.cache/npm" XDG_CACHE_HOME="$ROOT/.cache/xdg" PIP_CACHE_DIR="$ROOT/.cache/pip"
