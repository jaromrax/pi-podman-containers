#!/usr/bin/env bash
set -euo pipefail
PROJECT="omnivoice"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${1:-$ROOT/../${PROJECT}_source_${STAMP}.tgz}"
tar \
    --exclude='./.git' \
    --exclude='./.venv' \
    --exclude='./hf-cache' \
    --exclude='./output' \
    --exclude='./hello.wav' \
    -czf "$DEST" -C "$ROOT" .
echo "Created $DEST"
