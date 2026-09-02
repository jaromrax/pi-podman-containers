# Podman + FISPACT Container Setup

> Common rules: [`podman_readme_general.md`](../podman_readme_general.md)
>
> Project scripts: `podman_build.sh`, `podman_archive_source.sh`,
> `podman_archive_image.sh`

> **TODO(Podman):** Review and complete the source-archive exclusion list;
> FISPACT's generated and machine-local files have not yet been fully identified.

## 1. Podman Container Creation

### `podman_dockerfile_fispact`

The image is based on `docker.io/library/ubuntu:24.04` and built with:

```bash
./podman_build.sh
```

Key Dockerfile lessons:

- **Default user**: Ubuntu 24.04 already has a `ubuntu` user, so use `RUN id ubuntu || useradd -m -s /bin/bash ubuntu`
- **Install packages**: Use `apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*` in a single `RUN` to keep the image small
- **Install uv**: Download the prebuilt binary from Astral's releases and extract directly to `/usr/local/bin/` — `pip` is not available in the venv created by `uv`
- **Python venv**: Create with `uv venv /home/ubuntu/.venv` and install packages with `uv pip install --python /home/ubuntu/.venv/bin/python click pypact matplotlib`
- **Activate venv on login**: Append `source /home/ubuntu/.venv/bin/activate` to `/home/ubuntu/.bashrc`
- **File ownership**: After `COPY`-ing files into `/home/ubuntu/`, switch to `USER root`, run `chown -R ubuntu:ubuntu /home/ubuntu`, then switch back to `USER ubuntu`
- **Entry point**: `ENTRYPOINT ["uv", "run", "/opt/FispactII/fispact.py"]` makes the container run fispact.py directly

### Running the Container

```bash
# Run fispact.py on the current directory (projectile auto-detected)
podman run -v $(pwd):/home/ubuntu/workdir -w /home/ubuntu/workdir --userns=keep-id fispact

# Run with explicit projectile
podman run -v $(pwd):/home/ubuntu/workdir -w /home/ubuntu/workdir --userns=keep-id fispact h1

# Interactive shell
podman run -it -v $(pwd):/home/ubuntu/workdir -w /home/ubuntu/workdir --entrypoint bash fispact
```

- `-v $(pwd):/home/ubuntu/workdir` mounts the host working directory into the container
- `-w /home/ubuntu/workdir` sets the working directory inside the container
- `--userns=keep-id` maps the container user to the host UID so files written in the mount are owned by the host user (avoids `Permission denied` errors)

### Development Workflow

Edit `fispact.py` on the host, then run it inside the container without rebuilding:

```bash
podman run -it -v $(pwd):/home/ubuntu/workdir -w /home/ubuntu/workdir \
    --userns=keep-id --entrypoint bash fispact -lc "uv run ./fispact.py"
```

This mounts the current directory (containing your edited `fispact.py`) and runs it using the container's Python/venv. No image rebuild needed for code changes.

### Useful Podman Commands

```bash
podman images fispact                    # show image size
./podman_archive_source.sh
./podman_archive_image.sh
podman load -i ../fispact_image_YYYYMMDD_HHMMSS.tar  # restore an image archive
podman rmi fispact                              # remove image
```


### Archiving pipeline

 - build the image with `./podman_build.sh`
 - archive the source with `./podman_archive_source.sh`
 - archive the image with `./podman_archive_image.sh`
 - optionally compress the image archive with `pixz -9 ../fispact_image_YYYYMMDD_HHMMSS.tar`

---

## 2. FISPACT-in-a-Container: What You Need

### Minimal requirement: just `inventory.i`

The only file you need in your working directory is `inventory.i`. Everything else is handled automatically:

| What | How it's handled |
|------|-------------------|
| `fispact` binary | Found at `/opt/FispactII/fispact` |
| `fispact.py` | Runs from `/opt/FispactII/fispact.py` (container entry point) |
| `files` (cross-section config) | Auto-copied from `/opt/FispactII/opt_files_{proton\|deuteron\|neutron}` based on `PROJ N` line in `inventory.i` |
| `convert.i` | Auto-copied from `/opt/FispactII/convert.i` if not present |
| `collapse.i` | Auto-copied from `/opt/FispactII/collapse.i` if not present |
| `condense.i` | Auto-copied from `/opt/FispactII/condense.i` if not present |
| `spectra` | Auto-generated from `<<FORCE ENERGY N>>` directive in `inventory.i`, or from `-e N` flag |
| EAF data libraries | Already in `/opt/FispactII/EAF2007data/` and `/opt/FispactII/EAF2010data/` |

### How `fispact.py` Works Automatically

1. **Checks for `inventory.i`** in the current directory. Stops with error if missing.

2. **Auto-copies missing `.i` files** (`convert.i`, `collapse.i`, `condense.i`) from `/opt/FispactII/` to the current directory.

3. **Detects projectile** from the `PROJ N` line in `inventory.i` and copies the correct `opt_files_*` to `./files`:
   - `PROJ 1` → neutron → `opt_files_neutron`
   - `PROJ 2` → deuteron → `opt_files_deuteron`
   - `PROJ 3` → proton → `opt_files_proton`

4. **Auto-fixes PROJ lines** in `convert.i`, `collapse.i`, `condense.i` to match the detected projectile (in non-interactive/container mode).

5. **Handles `spectra`** via `<<FORCE ENERGY N>>` directive in `inventory.i`. For example:
   ```
   <<FORCE ENERGY 20.5>>
   ```
   This generates a single-energy `spectra` file at 20.5 MeV (for protons/deuterons). The `<<...>>` syntax is a FISPACT comment, so it is safely ignored by FISPACT itself and not removed from the file. The `<<FORCE ENERGY>>` directive takes priority over an existing `spectra` file — it will overwrite it without prompting.

6. **Logs everything** to `fispact_latest.log` in the current directory. Each line is prefixed with `HH:MM:SS -`.

7. **Runs the FISPACT stages**: convert → collapse → condense → inventory.

8. **Produces output**: `spectra.png`, `inventory.png`, `inventory.tab`, `inventory_<label>.tab`, plus FISPACT's own `.out` files.

### Typical `inventory.i` for Protons

```
NOHEAD
MONITOR 0
PROJ 3
GETXS 0
GETDECAY 0
FISPACT
* Cu 0.8960 g/cm2
DOSE 2 0.3
MASS 0.000896  1
CU 100.0
<<FORCE ENERGY 20.5>>
MIND 1.0E5
FLUX 6.24219725e+11
TIME 60 MINS
SPECTRUM
...
END
* END OF RUN
```

### Projectile Auto-Detection

The `projectile` argument is now optional. If omitted, it is auto-detected from the `PROJ N` line in `inventory.i`:

```bash
# Auto-detect projectile from inventory.i
podman run -v $(pwd):/home/ubuntu/workdir -w /home/ubuntu/workdir --userns=keep-id fispact

# Explicit projectile (overrides auto-detection)
podman run -v $(pwd):/home/ubuntu/workdir -w /home/ubuntu/workdir --userns=keep-id fispact h1
```

### Files Layout Inside the Container

```
/opt/FispactII/
    fispact              # FISPACT-II binary
    fispact.py           # Python wrapper script
    convert.i            # default convert input
    collapse.i           # default collapse input
    condense.i            # default condense input
    inventory.i           # default inventory input (reference)
    opt_files_proton     # cross-section config for PROJ 3
    opt_files_deuteron   # cross-section config for PROJ 2
    opt_files_neutron    # cross-section config for PROJ 1
    EAF2007data/          # nuclear data libraries
    EAF2010data/          # nuclear data libraries

/home/ubuntu/
    .venv/               # Python venv with click, pypact, matplotlib
    .bashrc              # venv auto-activation + fispact alias
```
