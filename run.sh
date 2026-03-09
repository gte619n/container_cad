#!/usr/bin/env bash
# Run cadbox from the project root
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate venv if not already active
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

cadbox serve "$@"
