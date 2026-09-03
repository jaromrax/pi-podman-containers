# Podman SRIM

> Common rules: [`podman_readme_general.md`](../podman_readme_general.md)
>
> Project scripts: `podman_build_srim.sh`, `podman_archive_source_srim.sh`,
> `podman_archive_image_srim.sh`

> **TODO(Podman):** Review and complete the source-archive exclusion list;
> SRIM's generated and machine-local files have not yet been fully identified.

This file is the repeatable reference for rebuilding the SRIM Podman image and understanding why the image is assembled this way.

## Purpose

- provide a stable Ubuntu + Wine + SRIM image
- keep SRIM installed inside the Wine prefix
- expose helper commands for backend execution
- keep host-mounted outputs writable by the host user

## Image Build

Build and archive the image from the project root:

```bash
./podman_build_srim.sh
./podman_archive_source_srim.sh
./podman_archive_image_srim.sh
```

## Basic Run

Interactive run with X11 passthrough:

```bash
podman run -it --rm \
    -v "$(pwd)":/home/ubuntu/workdir \
    -w /home/ubuntu/workdir \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    --userns=keep-id \
    srim
```

## Current Runtime Layout

Inside the image:

- SRIM install root:
  - `/home/ubuntu/.wine/drive_c/Program Files/SRIM`
- convenience symlink:
  - `/home/ubuntu/SRIM`
- SR Module convenience symlink:
  - `/home/ubuntu/SRIM_SR_Module`
- mounted host workdir:
  - `/home/ubuntu/workdir`

## Current Helper Commands

Installed in `/usr/local/bin/` during image build:

- `srim-run-srmodule`
- `srim-run-trim`

Important:

- these helpers are baked into the image
- if `container_helpers/srim-run-srmodule` or `container_helpers/srim-run-trim` changes, rebuild the image before testing

## Helper Behavior

### `srim-run-srmodule`

Expected inputs:

- job directory mounted under `/home/ubuntu/workdir`
- `SR.IN` present in that job directory

Behavior:

- parses output filename from line 3 of `SR.IN`
- copies `SR.IN` into `/home/ubuntu/SRIM_SR_Module`
- runs `wine SRModule.exe`
- copies the named output file back to the mounted job directory
- refuses overwrite by default
- requires `--force-clean` to replace an existing output file

### `srim-run-trim`

Expected inputs:

- `TRIM.IN`
- `TRIMAUTO`
- `TRIMAUTO` line 1 must be `1`

Behavior:

- copies `TRIM.IN` and `TRIMAUTO` into native `/home/ubuntu/SRIM`
- runs `TRIM.exe` there
- reads the `Diskfiles` line in `TRIM.IN`
- only expects and copies back outputs that were actually enabled
- refuses overwrite by default
- requires `--force-clean` to replace existing host-side result files

Important current rule:

- for the present workflow, `Transmit` in the `Diskfiles` line should remain `1`

## Why The Build Is Structured This Way

- Ubuntu 24.04 already ships a usable `ubuntu` user
- `wine32:i386` is needed because SRIM is an old Windows application
- `xvfb-run` is used both for Wine prefix initialization and for silent registration in build steps
- `uv` is installed directly to `/usr/local/bin` so Python tooling inside the image is simple and reproducible
- the unpacked SRIM tree is copied from `installation_files/SRIM_COPY/` instead of using an interactive installer at build time

## Enhanced `podman_dockerfile_srim`

Below is the current `podman_dockerfile_srim`, rewritten with explicit comments for maintenance reference.

```dockerfile
FROM docker.io/library/ubuntu:24.04

LABEL maintainer="SRIM Container"
LABEL description="SRIM - Stopping and Range of Ions in Matter"

# SRIM runs under Wine and needs 32-bit support.
# Keep apt update/install/cleanup in one layer.
RUN dpkg --add-architecture i386 && \
    apt-get update && apt-get install -y --no-install-recommends \
    wine \
    wine32:i386 \
    xvfb \
    ca-certificates \
    curl \
    nano \
    rsync less mc \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 already has user ubuntu, but keep this defensive check.
RUN id ubuntu || useradd -m -s /bin/bash ubuntu

# Install uv directly as standalone binaries.
RUN curl -sL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz | \
    tar xz -C /usr/local/bin --strip-components=1 \
    uv-x86_64-unknown-linux-gnu/uv \
    uv-x86_64-unknown-linux-gnu/uvx

# Python tools used inside the container.
# click is needed for CLI work; matplotlib is already in use in the repo.
USER ubuntu
RUN uv venv /home/ubuntu/.venv && \
    uv pip install --python /home/ubuntu/.venv/bin/python click matplotlib
RUN echo 'source /home/ubuntu/.venv/bin/activate' >> /home/ubuntu/.bashrc

# Initialize the Wine prefix in headless mode.
RUN xvfb-run wineboot --init && \
    wineboot --update && \
    rm -rf /home/ubuntu/.cache/wine

# Copy VB runtime / OCX dependencies into the Wine Windows tree.
COPY --chown=ubuntu:ubuntu \
    ./installation_files/COMDLG32.OCX \
    ./installation_files/msflxgrd.ocx \
    ./installation_files/MSVBVM50.DLL \
    ./installation_files/RICHTX32.OCX \
    ./installation_files/TABCTL32.OCX \
    ./installation_files/comctl32.ocx \
    /home/ubuntu/.wine/drive_c/windows/

# Copy the already-unpacked SRIM tree to a temporary path first.
COPY --chown=ubuntu:ubuntu ./installation_files/SRIM_COPY/ /tmp/srim_install/

# Move SRIM into "Program Files" and create convenience symlinks.
USER root
RUN mv /tmp/srim_install "/home/ubuntu/.wine/drive_c/Program Files/SRIM" && \
    chown -R ubuntu:ubuntu "/home/ubuntu/.wine/drive_c/Program Files/SRIM" && \
    ln -s "/home/ubuntu/.wine/drive_c/Program Files/SRIM" /home/ubuntu/SRIM && \
    ln -s "/home/ubuntu/.wine/drive_c/Program Files/SRIM/SR Module" /home/ubuntu/SRIM_SR_Module

# Register the legacy controls silently.
# The /s is critical: without it Wine may open a blocking modal dialog.
USER ubuntu
RUN xvfb-run -a sh -lc "\
    wineboot --update && \
    SRIMDIR='C:\\Program Files\\SRIM' && \
    wine regsvr32 /s \"\${SRIMDIR}\\MSVBVM50.DLL\" && \
    wine regsvr32 /s \"\${SRIMDIR}\\COMDLG32.OCX\" && \
    wine regsvr32 /s \"\${SRIMDIR}\\msflxgrd.ocx\" && \
    wine regsvr32 /s \"\${SRIMDIR}\\RICHTX32.OCX\" && \
    wine regsvr32 /s \"\${SRIMDIR}\\TABCTL32.OCX\" && \
    wine regsvr32 /s \"\${SRIMDIR}\\comctl32.ocx\" && \
    wineserver -k && \
    rm -rf /home/ubuntu/.cache/wine"

# Copy helper scripts late so helper-only edits do not invalidate early layers.
USER root
COPY container_helpers/srim-run-srmodule container_helpers/srim-run-trim /usr/local/bin/
RUN chmod 0755 /usr/local/bin/srim-run-srmodule /usr/local/bin/srim-run-trim

# Final ownership fix for Wine prefix, venv, and home.
RUN chown -R ubuntu:ubuntu /home/ubuntu
USER ubuntu

WORKDIR /home/ubuntu/workdir
```

## GOOD HABITS

- keep large, rarely changing `COPY` layers early
- keep helper scripts and fast-changing code late
- rebuild the image whenever helper scripts change
- use `--userns=keep-id` when mounting host directories
- use `xvfb-run -a` for non-interactive Wine build steps
- use silent `wine regsvr32 /s ...`
- use `uv pip install --python ...` inside the image rather than assuming `pip`
- preserve host files by parsing mounted inputs read-only when possible
- log backend steps to host-visible log files

## WHAT TO AVOID

- do not run `wine regsvr32` without `/s`
- do not assume every TRIM output file will exist; follow the `Diskfiles` switches in `TRIM.IN`
- do not forget that helper scripts are copied into the image; editing them alone does not update the running container
- do not write to mounted volumes without `--userns=keep-id`
- do not assume `pip` exists inside a `uv venv`
- do not use `uv tool install` for libraries such as `click`
- do not copy directly into a destination with spaces when a temp copy + `mv` is simpler
- do not treat Wine/X11 noise as the first explanation for a blocked build when a hidden modal dialog is more likely

## Rebuild Triggers

Rebuild the image after changes to:

- `podman_dockerfile_srim`
- `container_helpers/srim-run-srmodule`
- `container_helpers/srim-run-trim`
- `installation_files/*`
- `installation_files/SRIM_COPY/*`

## Minimal Repeat Procedure

1. Ensure `installation_files/` contains the required OCX/DLL files and `SRIM_COPY/`.
2. Build and archive:

```bash
./podman_build_srim.sh
./podman_archive_source_srim.sh
./podman_archive_image_srim.sh
```

3. Run interactively with X11:

```bash
podman run -it --rm \
    -v "$(pwd)":/home/ubuntu/workdir \
    -w /home/ubuntu/workdir \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    --userns=keep-id \
    srim
```

4. For backend checks, run the helpers against mounted test directories.
