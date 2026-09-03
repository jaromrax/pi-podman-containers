#!/usr/bin/env bash
set -euo pipefail
PROJECT="srim"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${1:-$ROOT/../podman_${PROJECT}_source_${STAMP}.tgz}"
# TODO(Podman): Review and complete this exclusion list; SRIM's generated and
# machine-local files have not yet been fully identified.
tar \
    --exclude='./.git' \
    --exclude='./.venv' \
    --exclude='./output' \
    --exclude='./work' \
    --exclude='./*.log' \
    -czf "$DEST" -C "$ROOT" .
echo "Created $DEST"
