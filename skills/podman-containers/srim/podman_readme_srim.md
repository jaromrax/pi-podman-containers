# Podman SRIM

> Common rules: [`podman_readme_general.md`](../podman_readme_general.md)
>
> Project scripts: `podman_build_srim.sh`, `podman_archive_source_srim.sh`,
> `podman_archive_image_srim.sh`
>
> Canonical Dockerfile: [`podman_dockerfile_srim`](podman_dockerfile_srim)
> (annotated; this readme does not duplicate it)

This file is the repeatable reference for rebuilding the SRIM Podman image and understanding why the image is assembled this way.

## Purpose

- provide a stable Ubuntu + Wine + SRIM image
- keep SRIM installed inside the Wine prefix
- expose helper commands for input generation, backend execution, and analysis
- keep host-mounted outputs writable by the host user
- pin the Python toolchain so reports are reproducible across rebuilds
- carry the image's own build sources, so it rebuilds from scratch anywhere

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
- input generation + analysis tools:
  - `/opt/srim-tools/input_creation/` (TRIM.IN / SR.IN generator)
  - `/opt/srim-tools/output_analysis/` (TRIM output parsers + report)
- reference host runners (run on the host, not in the container):
  - `/opt/srim-tools/host/srim_trim`, `/opt/srim-tools/host/srim_sr`
- container operating manual:
  - `/opt/srim-tools/INSTRUCTIONS.md`
- full build sources for rebuilding from scratch:
  - `/opt/srim-tools/host/building_container_sources/`
- build tag (UTC timestamp of last content change + python + base):
  - `/opt/srim-tools/BUILD_TAG.txt`
- mounted host workdir:
  - `/home/ubuntu/workdir`

## Current Helper Commands

Installed in `/usr/local/bin/` during image build:

- `srim-make-inputs` — generate `TRIM.IN` + `TRIMAUTO` + `SR[_i].IN`
- `srim-run-srmodule` — batch stopping-power run, copy output back
- `srim-run-trim` — batch TRIM run, copy enabled outputs back
- `srim-analyze` — print the TRIM summary table (`--save` writes it)

Important:

- these helpers are baked into the image
- if `container_helpers/*`, `container_input_creation/*`, or
  `container_output_analysis/*` changes, rebuild the image before testing

## Helper Behavior

### `srim-make-inputs`

Same flags as the legacy generator (`-i/-m/-t/-e/-a/-n/--dens/--pressure/
--kelvin/--rand/--outdir/--force-clean`). Writes CRLF files into the job
dir. No X11 needed (pure python).

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

Current fixed Diskfiles (set by the generator, not user options):

```text
1 0 1 0 0 0   (Ranges + Transmit only)
```

so a TRIM job produces `RANGE_3D.txt`, `TRANSMIT.txt`, `TRIMOUT.txt`
(plus `BACKSCAT.txt`/`SPUTTER.txt` only if enabled, always empty here).

### `srim-analyze`

Prints the summary table for a job dir (event counts, mean/median/sigma
for energy and depth, means for lateral Y/Z, theta mean/sigma/max in
degrees, radial sigma/max, emittance in pi·mm·mrad, header/TRIMOUT
checks). `--save output_table.txt` writes the table into the job dir.

## Why The Build Is Structured This Way

- Ubuntu 24.04 already ships a usable `ubuntu` user
- `wine32:i386` is needed because SRIM is an old Windows application
- `xvfb-run -a` is used for Wine prefix init, silent OCX registration,
  and headless TRIM runs (auto-picks a free virtual display)
- `uv` is installed directly to `/usr/local/bin` so Python tooling
  inside the image is simple; `uv venv --python 3.12` plus
  `uv pip install --python ... "pkg==x.y.z"` pins the toolchain
  (a `uv` venv has no `pip`; `uv tool install` is for CLIs, not libs)
- the unpacked SRIM tree is copied from
  `container_installation_files/SRIM_COPY/` instead of using an
  interactive installer at build time
- `uv pip install` lines pin exact versions (`click`, `matplotlib`,
  `pandas`) so analysis output cannot shift between rebuilds
- `BUILD_TAG.txt` is written by a `RUN date` layer placed after all
  `COPY` layers: layer caching then gives it exact semantics — the
  timestamp only refreshes when image content actually changed
- input/analysis sources are baked under `/opt/srim-tools/` and the
  build sources under `/opt/srim-tools/host/building_container_sources/`,
  so the image carries everything needed to reproduce or rebuild it
- `.dockerignore` excludes run dirs, caches, and tooling state to keep
  the build context small (timestamped job dirs accumulate fast)

## Wine Registration Gotcha

`wine regsvr32` must run with `/s`: without it Wine may open a blocking
modal dialog that hangs `podman build` while logs look merely noisy.
If silent registration still fails, suspect an invalid self-registration
target before suspecting X11 — e.g. `MSVBVM50.DLL` does not behave like
a normal regsvr32 target. Prefer `xvfb-run -a` over manually
backgrounding Xvfb.

## GOOD HABITS

- keep large, rarely changing `COPY` layers early
- keep helper scripts, tools, and docs late
- rebuild the image whenever helpers, tools, or install assets change
- use `--userns=keep-id` when mounting host directories
- use `xvfb-run -a` for non-interactive Wine build steps
- use silent `wine regsvr32 /s ...`
- use `uv pip install --python ... "pkg==version"` inside the image
  rather than assuming `pip`; pin versions that affect output
- record the content age of the image in a baked `BUILD_TAG` file
- ship the image's own build sources + operating manual inside the image
- preserve host files by parsing mounted inputs read-only when possible
- log backend steps to host-visible log files

## WHAT TO AVOID

- do not run `wine regsvr32` without `/s`
- do not assume every TRIM output file will exist; follow the `Diskfiles` switches in `TRIM.IN`
- do not forget that helpers and tools are copied into the image; editing them alone does not update the running container
- do not write to mounted volumes without `--userns=keep-id`
- do not assume `pip` exists inside a `uv venv`
- do not use `uv tool install` for libraries such as `click`
- do not use floating Python dependencies when the output must be reproducible
- do not copy directly into a destination with spaces when a temp copy + `mv` is simpler
- do not treat Wine/X11 noise as the first explanation for a blocked build when a hidden modal dialog is more likely

## Rebuild Triggers

Rebuild the image after changes to:

- `podman_dockerfile_srim` (i.e. the repo `Containerfile`)
- `container_helpers/srim-run-srmodule`
- `container_helpers/srim-run-trim`
- `container_helpers/srim-make-inputs`
- `container_helpers/srim-analyze`
- `container_input_creation/*`
- `container_output_analysis/*`
- `container_installation_files/*`
- `container_installation_files/SRIM_COPY/*`
- `srim_trim`, `srim_sr`, `INSTRUCTIONS.md` (baked as reference copies)

## Source Exclusions (archive + build context)

Known SRIM run/checkout files that must never be archived or sent as build
context: timestamped job dirs (`2026*/`), `.srim_runs/`, old test runs,
`tmp/`, `__pycache__/` (nested too — use `**/`), `.pi/`, `.agents/`,
`.codex/`, `.git/`, `*.log`, `*.~undo-tree~`. (Resolves the old TODO:
this list was identified from the live repo.)

## Minimal Repeat Procedure

1. Ensure `container_installation_files/` contains the required OCX/DLL
   files and `SRIM_COPY/`.
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

4. For backend checks, run the helpers against mounted test directories;
   verify `BUILD_TAG.txt` after rebuilds.
