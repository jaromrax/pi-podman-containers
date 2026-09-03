---
name: podman-containers
description: Build, run, document, and archive rootless Podman containers using shared rules and project-specific podman files. Use when creating or maintaining a project's Dockerfile, Podman build workflow, host mounts, DISPLAY/X11 sharing, source archives, or image archives.
license: MIT
---

# Podman Containers

This skill is the common operating procedure for the Podman project collection
in this repository. It contains no application source code. It contains shared
rules and the Podman files that document or package each supported project.

## Required reading order

1. Read [`podman_readme_general.md`](podman_readme_general.md).
2. Identify the target project example folder under `examples/`.
3. Read that folder's `podman_readme_<project>.md`.
4. Inspect the project's `podman_dockerfile_<project>` and scripts before
   changing or running them.

Do not infer project-specific mounts, generated files, display requirements,
or archive exclusions from another project.

## Project layout

Each project folder contains only its Podman integration files:

```text
<project>/
├── podman_readme_<project>.md
├── podman_dockerfile_<project>
├── podman_build_<project>.sh
├── podman_archive_source_<project>.sh
└── podman_archive_image_<project>.sh
```

The real application repository is not stored in this skill repository. The
project example folders contain only Podman files: they are starting points and
maintained knowledge. Their build context must be supplied by the real
application checkout when building.

Current project folders:

- [`omnivoice/`](omnivoice/)
- [`srim/`](srim/)
- [`fispact/`](fispact/)

## Operational rules

- Use the shared non-root `ubuntu` user in images.
- Use `--userns=keep-id` for rootless host-mounted work directories.
- Read and follow the project's mount instructions before running a container.
- Use read-only mounts for inputs whenever possible.
- Treat DISPLAY/X11 sharing as opt-in and follow the general security rules.
- Keep source and image archiving explicit: never archive unless the user asks.
- Review source-archive exclusions before claiming reproducibility.
- Record the source Git commit and image tag when archiving.
- Review any skill or script change before executing it; these files can run
  commands with full host access.

## Commands

From a project folder, the standard commands are (replace `<project>` with
that folder's project name):

```bash
./podman_build_<project>.sh
./podman_archive_source_<project>.sh
./podman_archive_image_<project>.sh
```

The archive scripts use `%Y%m%d_%H%M%S` timestamps. They archive outside the
project folder by default. They do not automatically call one another.
