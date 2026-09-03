#!/bin/bash

# ACTAR Podman build script
# Follows podman-containers skill compliance rules

set -e

echo "Building ACTAR container with explicit dockerfile selection..."
podman build -f podman_dockerfile_actar -t actar .

echo "Build completed. Image tagged as 'actar'"
echo "Verifying image..."
podman images | grep actar