#!/usr/bin/env bash
set -euo pipefail
PROJECT="srim"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${IMAGE:-$PROJECT}"
DOCKERFILE="$ROOT/podman_dockerfile_$PROJECT"
[[ -f "$DOCKERFILE" ]] || { echo "Missing $DOCKERFILE" >&2; exit 1; }
exec podman build -t "$IMAGE" -f "$DOCKERFILE" "$ROOT"
