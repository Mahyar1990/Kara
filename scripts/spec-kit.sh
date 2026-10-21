#!/usr/bin/env bash
# Project-local pinned tooling; never install into the application's Python environment.
set -euo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
if [[ "${1:-}" == bootstrap ]]; then
    command -v uv >/dev/null || { echo 'Install uv first (see docs/spec-driven-development.md).' >&2; exit 1; }
    mkdir -p .runtime/spec-kit
    export UV_CACHE_DIR="$ROOT/.runtime/spec-kit/uv-cache"
    export UV_TOOL_DIR="$ROOT/.runtime/spec-kit/tools"
    export UV_TOOL_BIN_DIR="$ROOT/.runtime/spec-kit/bin"
    uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@74be0a63e93c7087c5b06556b7561810d8f78a45
    "$UV_TOOL_BIN_DIR/specify" version
    exit 0
fi
if [[ ! -x .runtime/spec-kit/bin/specify ]]; then
    echo 'Run bash scripts/spec-kit.sh bootstrap first.' >&2
    exit 1
fi
exec .runtime/spec-kit/bin/specify "$@"
