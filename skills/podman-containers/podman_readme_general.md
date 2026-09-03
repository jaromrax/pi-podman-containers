# General Podman rules

This document is the common operating contract for every project directory in
this repository. It explains the practices that are safe to share; the
project README and its Dockerfile remain authoritative for application-specific
commands, mounts, entrypoints, devices, data, and tests.

## Repository layout

A project directory normally contains only its Podman integration and the
files needed by its build context:

```text
<project>/
├── podman_readme_<project>.md
├── podman_dockerfile_<project>
├── podman_build_<project>.sh
├── podman_archive_source_<project>.sh
└── podman_archive_image_<project>.sh
```

Some projects also contain application installation assets, helper scripts, or
host-side UI/wrapper scripts. Do not copy those files between projects or
assume that their runtime layouts are interchangeable. The real application
checkout may be the build context, or it may be mounted at runtime; read the
project README and inspect the build script first.

## Required reading and review order

1. Read this file.
2. Read `podman_readme_<project>.md`.
3. Inspect the project's Dockerfile and all build/run/archive scripts.
4. Check the build context and `.dockerignore` before building.
5. Review changes to scripts or Dockerfiles before executing them: they run
   commands with host or build-system privileges.

## Build

Run the project-provided build script rather than relying on an implicit
`Dockerfile` or `Containerfile`:

```bash
./podman_build_<project>.sh
```

The script must select `podman_dockerfile_<project>` explicitly and should use
an explicit build context. Unless the project says otherwise, the default image
tag is `<project>`; an alternate tag should be recorded with the preserved
source commit. A build does not start a container and does not archive anything.

Before building:

- confirm that all `COPY`/`ADD` inputs named by the Dockerfile are present;
- keep the context limited to intended files;
- exclude virtual environments, caches, generated output, credentials, Git
  metadata, and other unnecessary large files in `.dockerignore` where
  applicable;
- understand whether source is baked into the image or mounted for live
  development.

Good Dockerfile defaults are a small/pinned base where practical,
`--no-install-recommends`, one apt update/install/cleanup layer, and non-root
runtime execution. Pin important runtime dependencies, especially large ML or
compiler stacks, and avoid secrets in build arguments, layers, or copied files.

### Required system versions

When compilation or binary compatibility depends on the operating system,
preserve and document the required distribution and version; do not silently
upgrade the base image. For example, **ACTAR requires Ubuntu 22.04 to compile**
with its bundled ROOT and ACTAR dependencies.

## Runtime and host mounts

The project README must define the actual container entrypoint, workdir, and
required shares. A generic one-shot pattern is:

```bash
podman run --rm --userns=keep-id \
    -v "$(pwd)/input:/workdir/input:ro" \
    -v "$(pwd)/output:/workdir/output:Z" \
    -w /workdir \
    <image> [arguments]
```

Apply these rules unless a project-specific requirement overrides them:

- mount only the host paths the workload needs; keep source, input, output,
  cache, configuration, and devices separate;
- mount inputs read-only (`:ro`) whenever the application does not modify them;
- mount output explicitly so it survives `--rm` and container removal;
- use `--userns=keep-id` for rootless host-mounted work. It maps writes back to
  the invoking host user instead of creating inaccessible container-owned files;
- on SELinux, use `:Z` for a private mount and `:z` for a directory shared by
  multiple containers. On systems without SELinux the suffix may be omitted;
- quote paths and prefer absolute paths; remember that a mount hides image
  content already present at its destination;
- never mount the host home directory wholesale and never put credentials in
  an image or archive;
- keep model/package caches in deliberate host paths, not in source archives.

Use `--rm` for short-lived jobs. Use a named, long-running container only when
the project needs a service or an exec-based development workflow. Do not use
`--privileged`; pass only explicitly required devices, ports, and environment.

## GUI, X11, and headless display

Display access is opt-in. Headless containers should not receive host display
sockets. For an X11 application, the project may use:

```bash
podman run --rm -it --userns=keep-id \
    -e DISPLAY="${DISPLAY}" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    <image>
```

Verify that `DISPLAY` is set. Avoid persistent broad `xhost +` permissions;
use the host's normal authorization mechanism and remove temporary access
when finished. Wayland/native socket sharing is project-specific; XWayland may
be required for the example above.

For build steps or automated GUI programs that only need a display, use a
virtual framebuffer inside the image:

```bash
xvfb-run -a <command>
```

Install `xvfb` only when required, and use silent/non-interactive application
flags where a modal dialog could block a build.

## Test and troubleshoot

Every project should document a cheap smoke test before expensive downloads or
long computations. A useful sequence is:

1. verify the image exists and inspect its tag;
2. run the project's `--help`, version, or minimal input test;
3. verify input/output ownership on the host;
4. for services, check `podman ps`, published ports, and `podman logs`;
5. for exec-based workflows, confirm the container is running and inspect the
   project log/status file;
6. enter a diagnostic shell only as documented by the project, for example
   `podman run --rm -it --entrypoint bash <image>`.

For mount permission failures, check `--userns=keep-id` and SELinux labels
before changing host permissions. For missing files, first check whether a
mount is hiding files baked into the image. For GUI hangs, suspect a missing
X display or a hidden modal dialog. Do not run image-specific binaries directly
on the host unless the project explicitly supports that workflow.

## Source and image archives

Archiving is a deliberate, separate operation. Build, run, UI, and compile
commands must not archive automatically. Use both kinds when preserving a
working state:

```bash
./podman_archive_source_<project>.sh
./podman_archive_image_<project>.sh
```

The source archive preserves the recipe and required build inputs. The image
archive preserves the already-built runtime and is restored with:

```bash
podman load -i <image-archive>.tar
```

Archive scripts choose their own exact filename, compression, exclusions, and
destination (the supplied scripts normally write outside the project
folder). Do not assume every project uses the same historical prefix; inspect
the script. Current conventional names are:

```text
podman_<project>_source_<YYYYMMDD_HHMMSS>.tgz
podman_<project>_image_<YYYYMMDD_HHMMSS>.tar
```

The source exclusions must be reviewed for each project. Exclude Git metadata,
virtual environments, dependency/model caches, logs, generated output,
build products, credentials, and host-only data unless they are intentionally
part of the reproducible input. Never claim reproducibility without checking
that the Dockerfile's `COPY`/`ADD` inputs are actually included.

Record, alongside the archive or in release notes:

- source Git commit (`git rev-parse HEAD`);
- image tag, image ID/digest, and base/dependency versions;
- host architecture and any required GPU/runtime assumptions;
- the test command and result;
- archive exclusions and any external input assets needed to rebuild.

A source archive reproduces a recipe, not necessarily remote registries or
large external data. An image archive avoids rebuilding from changed registries
but does not include host-mounted data, caches, or volumes unless explicitly
saved separately.

## Change and release checklist

Before committing or preserving a project:

- update the project README when mounts, names, entrypoints, or workflow change;
- rebuild after Dockerfile, copied helper, dependency/lockfile, or baked-source
  changes; mounted source changes generally need no rebuild;
- run the documented smoke test and, for services, verify shutdown/cleanup;
- check ownership of generated host files and that no secret or large cache was
  copied into the context;
- review source-archive exclusions;
- record commit, image identity, test result, and archive locations;
- archive source and image only after an explicit user decision.

The general README should stay generic. Project-specific exceptions belong in
that project's `podman_readme_<project>.md`, not here.
