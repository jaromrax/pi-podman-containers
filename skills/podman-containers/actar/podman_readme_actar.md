# ACTAR Podman integration

Project-specific operating instructions for the ACTAR Ubuntu 22.04 container.
This container is a long-running development/runtime service, not a one-shot
batch image.

## Files

- `podman_dockerfile_actar` — image recipe; Ubuntu 22.04 and ROOT 6.30
- `podman_build_actar.sh` — explicit build, tag `actar`
- `podman_ui_actar.py` — host UI for shares and container lifecycle
- `podman_compile_and_run_actar.sh` — host wrapper using `podman exec`
- `podman_archive_source_actar.sh` / `podman_archive_image_actar.sh` — explicit archives

## Important separation

The image contains the complete ACTAR project and its original reference
`root/` directory at:

```text
/home/ubuntu/ACTAR/analysis_code/root
```

This internal `root/` is rebuilt from `full_actar_folder_structure.tar.gz`.
Until that archive changes, every image build recreates the same internal
snapshot. It is retained as a reference and backup of one point in time; it is
not the active development directory. The host's actively edited `root/` is
mounted separately as:

```text
/home/ubuntu/ACTAR/analysis_code/root_remote
```

Compile and run the host code inside the container. Do not run the generated
`main` directly on the host: it needs the container's compiler, ROOT, ACTAR
libraries, and library search environment. Always source
`/home/ubuntu/root/bin/thisroot.sh` before compiling or running.

## Shares

| Host path | Container path | Mode | Purpose |
|---|---|---|---|
| `root/` | `/home/ubuntu/ACTAR/analysis_code/root_remote` | `rw,Z` | Active source/build |
| `DATA/` | `/home/ubuntu/data` | `ro,Z` | Large input data |
| `TrackOutput/` | `/home/ubuntu/TrackOutput` | `rw,Z` | Trees, images, output |
| `actar.ini` | `/home/ubuntu/actar.ini` | `ro,Z` | Runtime configuration |

Use `--userns=keep-id`; never use `--privileged`.

## Workflow

Install and run the host UI with Astral uv:

```bash
uv tool install --editable .
podman-ui-actar
```

The UI reports image `actar`, container `running_actar`, and the last compile
status. It polls `root/podman_compile_result.txt` every two seconds. Missing
shares are red; select a row and press `e` to choose a directory or `*.ini`
file. The UI never builds implicitly. Build explicitly:

```bash
./podman_build_actar.sh
# or: uv run podman_ui_actar.py --build
```

Manual connection:

```bash
podman exec -it running_actar bash
```

## Compile/run wrapper

From the host `root/` directory:

```bash
../podman_compile_and_run_actar.sh -h
../podman_compile_and_run_actar.sh       # make
../podman_compile_and_run_actar.sh 277   # canonical smoke run
../podman_compile_and_run_actar.sh 300   # any run number
../podman_compile_and_run_actar.sh -x    # make clean only; standalone
```

The wrapper writes `podman_compile_result.txt` in the current host `root/`
directory: `RUNNING`, `OK`, or `FAIL`. Run 277 is only a canonical test, not a
restriction.

If `./main` reports `libACTARshared.so` missing, the executable was likely run
outside the container, compilation failed, or the ROOT/ACTAR environment was
not sourced. Inspect `podman_ui_actar.log` and rerun compilation through the
wrapper.

## Diagnostics and archives

The UI writes the single append-only diagnostic log `podman_ui_actar.log` next
to the UI script. It records Podman commands, output, errors, and return codes.
Archives are explicit and written outside the source tree:

```bash
./podman_archive_source_actar.sh
./podman_archive_image_actar.sh
```

Update this file and the repository's `README_actar.md` together when changing
mounts, names, image assumptions, or workflow behavior.
