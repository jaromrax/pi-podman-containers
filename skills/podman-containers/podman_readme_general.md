# General Podman Rules

This is the common operating standard for all project containers. Each project
has a project-specific `podman_readme_<project>.md`, a
`podman_dockerfile_<project>`, and three project-prefixed scripts because the
projects coexist in this repository:

- `podman_build_<project>.sh`
- `podman_archive_source_<project>.sh`
- `podman_archive_image_<project>.sh`

All project integration files use the project name in the filename; replace
`<project>` below with the actual project name.

## Build

Build from the project root and tag the image with the project name:

```bash
./podman_build_<project>.sh
```

The build script must select `podman_dockerfile_<project>` explicitly. Do not
rely on an implicit or accidentally selected Dockerfile.

## Source archive

A source archive preserves the Dockerfile, source, lockfiles, scripts,
configuration, and project documentation needed to reproduce a build. Each
project's source-archive script contains its own exclude list directly, so the
three scripts are self-contained and there are no separate `.excludes` files.
Archive names use the project-prefixed format and local timestamp:

```text
podman_<project>_source_<timestamp>.tgz
podman_<project>_image_<timestamp>.tar

# timestamp: %Y%m%d_%H%M%S
```

## Image archive

The source archive preserves the recipe; the image archive preserves the
actual built runtime. Keep both for reliable long-term reproducibility:

```bash
./podman_archive_source_<project>.sh
./podman_archive_image_<project>.sh
```

Image archives are created with `podman save` and restored with `podman load`.
Store archives outside the source tree, preferably on a dedicated archive
volume or other dry storage.

**Archiving is always an explicit user action.** None of the build, run, or
application commands archives source or images automatically. The user decides
when a source snapshot or image snapshot is sufficiently stable to preserve and
must invoke the archive scripts deliberately:

```bash
./podman_archive_source_<project>.sh
./podman_archive_image_<project>.sh
```

## Host directory sharing

Host sharing is part of the standard runtime contract, not an incidental
project detail. A project-specific README should document its required mounts,
but these rules apply to every project:

```bash
podman run --rm --userns=keep-id \
    -v "$(pwd)/input:/workdir/input:ro" \
    -v "$(pwd)/output:/workdir/output:Z" \
    -w /workdir \
    <image>
```

- Mount only the directories the workload needs; prefer separate input,
  output, cache, and source mounts.
- Mount inputs read-only (`:ro`) whenever the application does not need to
  modify them.
- Mount generated output explicitly so it survives container removal.
- Use `--userns=keep-id` for rootless containers so files created in a host
  mount map back to the invoking host user instead of becoming inaccessible.
- On SELinux systems, use `:Z` for a private container mount or `:z` when the
  same directory is shared by multiple containers. Do not disable labeling as
  a first response to a permissions problem.
- Use absolute paths or quote `$(pwd)`; do not depend on a caller's current
  directory accidentally matching the container work directory.
- Never mount sensitive host directories such as the home directory wholesale.
- Keep model, package, and application caches in named host paths, and exclude
  those caches from source archives unless intentionally preserving them.
- Remember that a mounted host path hides any image content at the same path.
- If an application needs temporary scratch space, use a separate temporary
  mount or container path rather than writing beside source inputs.

## Display sharing and graphical applications

A container that needs to display a GUI on the host must receive both the
host's display identifier and the X11 Unix socket. This is an opt-in mount; do
not add it to headless containers unnecessarily:

```bash
podman run --rm -it \
    --userns=keep-id \
    -e DISPLAY="${DISPLAY}" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    <image>
```

- Check that the host `DISPLAY` variable is set before starting the container.
- Mount `/tmp/.X11-unix` read-only; the socket is the bridge to the host X
  server, not application data.
- GUI access is a host capability. Avoid broad, persistent `xhost +` rules;
  use the host's normal X authorization mechanism and remove any temporary
  authorization after use.
- Keep `--userns=keep-id` even for GUI containers so files written to mounted
  work directories retain the host user's ownership.
- Wayland hosts may require an XWayland session for this X11 pattern; native
  Wayland socket sharing is a separate, project-specific configuration.
- For builds and automated jobs that need a display but not a visible window,
  use a virtual framebuffer inside the image:

```bash
xvfb-run -a <command>
```

  Install `xvfb` in the image when this is required. In build steps, use
  `xvfb-run -a` for deterministic headless operation and use silent flags for
  tools that otherwise open modal dialogs.

## Runtime rules

- Use the shared non-root `ubuntu` user in every image.
- Use `--userns=keep-id` for rootless host-mounted work directories.
- Mount only required input/output, cache, and device paths.
- Use `:Z` or `:z` volume labels on SELinux hosts as appropriate.
- Do not use `--privileged`; request only required devices.
- Keep model/data caches outside the image unless deliberately archiving them.
- Keep credentials out of Dockerfiles, source archives, and image layers.
- Combine apt update/install/cleanup in one layer.
- Pin important dependency versions and record the source Git commit.
- Use `--rm` for one-shot jobs and persistent named containers only for services.
- Test the image with `--help` before downloading large models or datasets.

## Rebuild and archive sequence

1. Check the project source and lockfiles.
2. Build with the project build script.
3. Run a smoke test.
4. Record `git rev-parse HEAD` and the image tag.
5. Archive the source.
6. Archive the image.

The build context must contain only the intended project files. Maintain a
`.dockerignore` to exclude virtual environments, caches, generated output,
credentials, and other unnecessary material.
