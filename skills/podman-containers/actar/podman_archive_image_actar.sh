#!/bin/bash

# ACTAR image archive script (project-specific)
# Archives the built container image for long-term preservation

set -e

# Get current timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="podman_actar_image_${TIMESTAMP}.tar"

# Image name
IMAGE_NAME="actar"

# Check if image exists
if ! podman image exists "$IMAGE_NAME"; then
    echo "Error: Image '$IMAGE_NAME' not found. Please build it first with ./podman_build_actar.sh"
    exit 1
fi

echo "Archiving image: $IMAGE_NAME"
echo "Archive name: $ARCHIVE_NAME"

# Create image archive
podman save -o "../$ARCHIVE_NAME" "$IMAGE_NAME"

echo "Image archive created: ../$ARCHIVE_NAME"
echo "Archive size:"
ls -lh "../$ARCHIVE_NAME"

# Record image details
IMAGE_ID=$(podman images --format "{{.ID}}" "$IMAGE_NAME" | head -n1)
echo "Image ID: $IMAGE_ID"

# If git is available, record the source commit
if command -v git &> /dev/null && [ -d .git ]; then
    GIT_COMMIT=$(git rev-parse HEAD)
    echo "Source git commit: $GIT_COMMIT"
fi

echo ""
echo "To restore this image later, use:"
echo "  podman load -i $ARCHIVE_NAME"