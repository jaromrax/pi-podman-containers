#!/bin/bash

# ACTAR source archive script (project-specific)
# Archives source code, configuration, and build files for reproducibility

set -e

# Get current timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="podman_actar_source_${TIMESTAMP}.tar.gz"

# Record current git commit
if command -v git &> /dev/null && [ -d .git ]; then
    GIT_COMMIT=$(git rev-parse HEAD)
    echo "Git commit: $GIT_COMMIT" > git_commit.txt
    echo "Archiving source at git commit: $GIT_COMMIT"
fi

echo "Creating source archive: $ARCHIVE_NAME"

# Create archive with exclusions for ACTAR project
tar -czf "../$ARCHIVE_NAME" \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='*.tmp' \
    --exclude='*.log' \
    --exclude='node_modules' \
    --exclude='venv' \
    --exclude='.venv' \
    --exclude='.pi' \
    --exclude='skill_actar' \
    --exclude='build' \
    --exclude='dist' \
    --exclude='.pytest_cache' \
    --exclude='.coverage' \
    --exclude='*.egg-info' \
    --exclude='TrackOutput/*' \
    --exclude='root_readonly' \
    --exclude='DATA/*' \
    --exclude='Tree_*.root' \
    --exclude='podman_ui_actar.log' \
    --exclude='podman_actar_config.json' \
    --exclude='podman_compile_result.txt' \
    --exclude='*.~undo-tree~' \
    --exclude='*~undo-tree~' \
    --exclude='*.o' \
    --exclude='*.pcm' \
    --exclude='*.so' \
    --exclude='root/main' \
    .

echo "Source archive created: ../$ARCHIVE_NAME"
echo "Archive size:"
ls -lh "../$ARCHIVE_NAME"

# Clean up temporary git commit file
if [ -f git_commit.txt ]; then
    rm git_commit.txt
fi