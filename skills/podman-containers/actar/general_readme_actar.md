# ACTAR Podman: development and run knowledge

This document records the decisions and operating habits for the ACTAR
container. It is intentionally more important than a quick-start README: a
future developer should read it before changing mounts, the image, or the
compile/run workflow.

## Purpose and architecture

This is not a one-shot container. The image is a **service for development and
running ACTAR code**:

- Ubuntu 22.04 is mandatory for compatibility with the bundled ROOT 6.30
  installation and ACTAR dependencies.
- The complete ACTAR project and its compiled support libraries are built into
the image.
- The host `root/` directory contains the actively edited analysis code. It is
  mounted inside the container as `root_remote` and compiled there.
- The image's original `/home/ubuntu/ACTAR/analysis_code/root` is deliberately
  kept separate from host `root/`. Do not mount host `root/` over that image
  directory.
- Large input data and generated output stay on the host and are mounted into
  the running container.
- `actar.ini` is a host-controlled, read-only runtime configuration.

The host-side compile/run command interacts with the long-running container
using `podman exec`. The compiler, ROOT, ACTAR libraries, and runtime
environment therefore come from the container, while source edits and data
remain on the host.

## Canonical files

The maintained Podman integration files are also copied into `skill_actar/`:

- `podman_dockerfile_actar` — Ubuntu 22.04 image recipe
- `podman_build_actar.sh` — explicit image build
- `podman_ui_actar.py` — interactive share/container UI
- `podman_compile_and_run_actar.sh` — important host-side compile/run wrapper
- `podman_archive_source_actar.sh` — explicit source archive
- `podman_archive_image_actar.sh` — explicit image archive
- `podman_readme_actar.md` — specialized project instructions

The image is tagged `actar`; the long-running container is named
`running_actar`.

## Host layout and shares

Expected host paths, relative to this repository:

```text
root/         actively developed code, compiled in the container
DATA/         large input data, mounted read-only
TrackOutput/  trees, images, and other generated output
actar.ini     runtime configuration, mounted read-only
```

Container mounts:

```text
root/        -> /home/ubuntu/ACTAR/analysis_code/root_remote  rw,Z
DATA/        -> /home/ubuntu/data                            ro,Z
TrackOutput/ -> /home/ubuntu/TrackOutput                     rw,Z
actar.ini    -> /home/ubuntu/actar.ini                       ro,Z
```

The container must use `--userns=keep-id`. This keeps files written to host
mounts owned by the invoking host user. Do not use `--privileged`; use only the
required mounts and devices.

## Normal workflow

Install the host UI as an Astral `uv` tool:

```bash
uv tool install --editable .
```

Start the UI:

```bash
podman-ui-actar
```

The UI shows three live indicators: whether image `actar` exists, whether
`running_actar` is running, and the latest compile result. Select a share and
press `e` to open its path/file picker. The UI does not build an image
implicitly. Build only by explicit user action:

```bash
./podman_build_actar.sh
# or
uv run podman_ui_actar.py --build
```

Use the UI's Start/Restart and Stop controls. When quitting, it asks whether a
running container should be stopped and removed; if it is already stopped, no
question is asked.

A manually opened shell is:

```bash
podman exec -it running_actar bash
```

## Compile and run

The active code is compiled inside the already-running container. From the
host repository's `root/` directory:

```bash
cd root
../podman_compile_and_run_actar.sh -h
../podman_compile_and_run_actar.sh       # compile only
../podman_compile_and_run_actar.sh 277   # compile and run canonical test
../podman_compile_and_run_actar.sh 300   # any other run number
```

The wrapper expects `main.C` in the current directory. It executes `make` and
`make run` through `podman exec`, after sourcing:

```text
/home/ubuntu/root/bin/thisroot.sh
```

Run `277` is only a canonical smoke/test run; it is not a special limitation.
Other run numbers are supported. `-x` is deliberately standalone and performs
only a clean:

```bash
../podman_compile_and_run_actar.sh -x
```

Do not confuse the host source directory `root/` with the image ROOT
installation. If the executable reports:

```text
error while loading shared libraries: libACTARshared.so
```

first ensure compilation completed successfully in the container, that the
command sourced `thisroot.sh`, and that the generated libraries are in the
host-mounted `root_remote` build location expected by the Makefile. Running
`./main` directly on the host is not supported: it lacks the container's ROOT,
compiler, library search paths, and dependencies.

## Compilation result and diagnostics

`podman_compile_and_run_actar.sh` writes this status file in host `root/`:

```text
root/podman_compile_result.txt
```

It records `RUNNING`, `OK`, or `FAIL`. The UI polls it every two seconds and
shows the latest compilation state. This is a status indicator, not a complete
build log.

The UI appends Podman diagnostics to:

```text
podman_ui_actar.log
```

The log includes commands, stdout/stderr captured from Podman, return codes,
image checks, and startup failures. Check it first when the UI cannot start or
when the image/container state is surprising.

## Reproducibility and archiving

Archiving is always explicit. Do not archive automatically from build, run, or
UI commands:

```bash
./podman_archive_source_actar.sh
./podman_archive_image_actar.sh
```

Archives are written outside the source tree. Record the source Git commit and
image tag when preserving a working state. Do not archive host data, generated
output, UI logs, virtual environments, credentials, or build artifacts as
source unless deliberately required.

## Rules for future changes

1. Preserve Ubuntu 22.04 unless ROOT/ACTAR compatibility is revalidated.
2. Keep the non-root image user named `ubuntu`.
3. Keep image `root` and host `root_remote` separate.
4. Keep `DATA` read-only and output explicitly mounted.
5. Keep `actar.ini` host-mounted and read-only.
6. Test the full sequence: build, start, compile, canonical run 277, another
   run number, and stop.
7. Update both this document and the maintained copy under `skill_actar/` when
   mount paths or workflow decisions change.
8. Review archive exclusions before claiming reproducibility.
