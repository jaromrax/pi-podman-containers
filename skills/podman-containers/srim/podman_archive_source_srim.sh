#!/usr/bin/env bash
set -euo pipefail
PROJECT="srim"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${1:-$ROOT/../podman_${PROJECT}_source_${STAMP}.tgz}"
# Exclusion list identified from the live repo: timestamped job dirs,
# run caches, tooling state, logs, editor backups. (TODO resolved 2026-11.)
tar \
    --exclude='./.git' \
    --exclude='./.venv' \
    --exclude='./__pycache__' \
    --exclude='./*/__pycache__' \
    --exclude='./output' \
    --exclude='./work' \
    --exclude='./tmp' \
    --exclude='./.srim_runs' \
    --exclude='./2026*' \
    --exclude='./test_20261104' \
    --exclude='./.pi' \
    --exclude='./.agents' \
    --exclude='./.codex' \
    --exclude='./*.log' \
    --exclude='./*.~undo-tree~' \
    -czf "$DEST" -C "$ROOT" .
echo "Created $DEST"
