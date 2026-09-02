#!/usr/bin/env bash
set -euo pipefail
PROJECT="srim"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${IMAGE:-$PROJECT}"
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${1:-$ROOT/../${PROJECT}_image_${STAMP}.tar}"
podman image exists "$IMAGE" || { echo "Image $IMAGE does not exist; build it first" >&2; exit 1; }
podman save "$IMAGE" -o "$DEST"
echo "Created $DEST"
