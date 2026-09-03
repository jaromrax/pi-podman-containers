# OmniVoice with Podman

> Common rules: [`podman_readme_general.md`](../podman_readme_general.md)
>
> Project scripts: `podman_build_omnivoice.sh`, `podman_archive_source_omnivoice.sh`,
> `podman_archive_image_omnivoice.sh`

This document is the repeatable reference for building and running OmniVoice in
Podman. It combines general container-maintenance practices with an OmniVoice-
specific README. The supplied [`podman_dockerfile_omnivoice`](podman_dockerfile_omnivoice) is intentionally
Docker-compatible and can be built with Podman.

## What this image provides

- OmniVoice single-item TTS via `omnivoice-infer`
- the Python API and the Gradio demo (`omnivoice-demo`)
- CPU PyTorch by default, suitable for this host and portable rootless runs
- the shared non-root `ubuntu` runtime user used by the other project containers
- persistent Hugging Face model caching when `/models` is mounted
- host-writable audio output when `--userns=keep-id` is used

The image does **not** contain the model weights. They are downloaded on the
first invocation and should normally be stored in a host-mounted cache.

OmniVoice **is installed into the image**: `podman_dockerfile_omnivoice` copies the checked-out
`omnivoice/` package into `/opt/omnivoice` and runs `uv pip install --no-deps
/opt/omnivoice`. Its dependencies are installed in the preceding layer; this
split is deliberate so the CPU PyTorch wheels are selected instead of the
repository's Linux CUDA lockfile entries.

## Build

From the OmniVoice project root:

```bash
./podman_build_omnivoice.sh
```

Smoke-test the image without downloading model weights:

```bash
podman run --rm omnivoice
```

Check the installed CLI explicitly:

```bash
podman run --rm omnivoice --help
```

## CPU single-sentence TTS

The default entrypoint is `omnivoice-infer`, so arguments can be passed
straight to the image:

```bash
mkdir -p output hf-cache
podman run --rm --userns=keep-id \
    -v "$(pwd)/output:/workdir:Z" \
    -v "$(pwd)/hf-cache:/models:Z" \
    omnivoice \
    --model k2-fsa/OmniVoice \
    --text "Hello from OmniVoice in a container." \
    --output /workdir/hello.wav \
    --device cpu
```

Use `:z` instead of `:Z` when the cache or output directory is shared by
multiple containers. On systems without SELinux, the suffix can be omitted.

### Voice design

```bash
podman run --rm --userns=keep-id \
    -v "$(pwd)/output:/workdir:Z" -v "$(pwd)/hf-cache:/models:Z" \
    omnivoice \
    --text "This is a British voice design example." \
    --instruct "male, British accent" \
    --output /workdir/design.wav \
    --device cpu
```

### Voice cloning

```bash
podman run --rm --userns=keep-id \
    -v "$(pwd):/workdir:Z" -v "$(pwd)/hf-cache:/models:Z" \
    omnivoice \
    --text "This sentence uses the reference speaker." \
    --ref_audio /workdir/ref.wav \
    --ref_text "The transcription of the reference audio." \
    --output /workdir/cloned.wav \
    --device cpu
```

`--ref_text` may be omitted to enable Whisper auto-transcription. That causes
an additional ASR model download; supplying the transcription is faster and
more reproducible.

## Running the persistent demo server

The server keeps the OmniVoice model resident, so it is preferable to starting
one container per sentence. Override the image entrypoint:

To launch Gradio, override the image entrypoint:

```bash
podman run --rm --userns=keep-id \
    -p 8001:8001 \
    -v "$(pwd)/hf-cache:/models:Z" \
    --entrypoint omnivoice-demo \
    omnivoice \
    --ip 0.0.0.0 --port 8001 --device cpu
```

Open `http://localhost:8001`. For repeated automated requests, load
`OmniVoice` once in a long-lived Python service rather than invoking the
single-item CLI repeatedly; the CLI reloads the model for every process.

A minimal shell for the API/runtime is also available:

```bash
podman run --rm -it --entrypoint bash omnivoice
```

## NVIDIA GPU variant

The checked-in `podman_dockerfile_omnivoice` is CPU-first because it avoids shipping several
GiB of CUDA libraries and works on machines without NVIDIA support. For GPU
inference, use a CUDA-enabled PyTorch base/runtime and install matching
`torch`/`torchaudio` wheels from the PyTorch CUDA index. The host must also
have an installed NVIDIA Container Toolkit:

```bash
podman run --rm --device nvidia.com/gpu=all \
    -v "$(pwd)/hf-cache:/models:Z" -v "$(pwd)/output:/workdir:Z" \
    omnivoice --device cuda:0 --text "GPU test" --output /workdir/gpu.wav
```

Do not mix a CUDA PyTorch wheel with a CPU image or an incompatible host driver.
Keep a separate GPU Dockerfile/tag rather than making the CPU image ambiguous.

## Container construction principles

### Reproducibility

- Build from a pinned, small base image where practical.
- Pin the PyTorch major/minor version and use the repository lockfile as the
  reference for source dependency changes.
- Keep the image build context small; do not copy `.venv`, model caches, audio
  outputs, or credentials. Add them to `.dockerignore` if this image is built
  outside the current checkout.
- Record the source commit and image tag when archiving an image.

### Image hygiene

- Combine `apt-get update`, installation, and cleanup in one layer.
- Use `--no-install-recommends` and avoid build tools in the runtime image.
- Use `uv` as an installer, not as a reason to retain a package cache in the
  final image.
- Copy frequently changing source late where it improves rebuild times.
- Keep model weights in a mounted cache rather than baking them into the image.

### Runtime safety and data ownership

- Run as the shared non-root `ubuntu` user (matching the SRIM and FISPACT
  containers).
- Mount only the directories required for input/output and model cache.
- Use `--userns=keep-id` for rootless Podman host mounts so generated WAV files
  belong to the invoking host user.
- Prefer `--rm` for short-lived jobs and explicit named containers only for
  long-running services.
- Do not use `--privileged`; request only the GPU device, port, and volumes
  needed by the workload.
- Never put Hugging Face tokens or other secrets in the project Dockerfile or image
  layers.

### Operations and troubleshooting

- Keep model/cache, input/output, and application code in distinct paths.
- Name image tags with a meaningful version or source commit.
- Inspect logs with `podman logs`; enter a shell with `--entrypoint bash`.
- If a mounted directory is not writable, check `--userns=keep-id` and SELinux
  labels (`:Z`/`:z`) before changing permissions.
- If model downloads fail behind a restricted network, pass a suitable
  `HF_ENDPOINT` and persist `/models` so retries do not repeat downloads.
- CPU generation is functional but slow. Use a persistent process for many
  sentences and a CUDA image/device for production throughput.

## Reproducible source archive and image archive

The `podman_dockerfile_omnivoice` installs the source from the build context. Therefore, preserve
the complete source/build directory if the image must be reproducible later.
The nested path `/opt/omnivoice/omnivoice/` is intentional: the first directory
is the project root containing `pyproject.toml`, and the second is the Python
package directory.

Create a source archive from the project root. The project-specific script
contains OmniVoice's exclude list directly, so no separate exclude file is
needed:

```bash
./podman_archive_source_omnivoice.sh
```

It includes `podman_dockerfile_omnivoice`, the lockfile, package source, and
Podman documentation while excluding the local virtual environment, model
cache, generated output, and Git metadata.

For an exact code state, also record the Git commit:

```bash
cd /path/to/omnivoice
GIT_CONFIG_GLOBAL=/dev/null git rev-parse HEAD
```

Archive the already-built image separately. This is the most reliable way to
run the same dependencies without rebuilding from potentially changed remote
registries:

```bash
./podman_archive_image_omnivoice.sh
# Optional compression (use the timestamped file it creates):
pixz -9 ../podman_omnivoice_image_YYYYMMDD_HHMMSS.tar
# Restore later:
podman load -i ../podman_omnivoice_image_YYYYMMDD_HHMMSS.tar
```

The source archive reproduces the build recipe and source; the image archive
preserves the actual built runtime. Neither archive contains the Hugging Face
model cache unless it is deliberately added separately.

## Updating and rebuilding

Rebuild after changes to:

- `podman_dockerfile_omnivoice`
- `pyproject.toml` or `uv.lock`
- the `omnivoice/` source tree

```bash
IMAGE=omnivoice:$(git rev-parse --short HEAD) ./podman_build_omnivoice.sh
```

Useful image commands:

```bash
podman images omnivoice
podman inspect omnivoice
./podman_archive_image_omnivoice.sh
podman load -i ../podman_omnivoice_image_YYYYMMDD_HHMMSS.tar
podman rmi omnivoice
```

## Known limitations

- The default image is CPU-only; it does not provide CUDA acceleration.
- Model weights are downloaded at runtime rather than during build.
- The Gradio demo is a web UI, not a stable REST API. For programmatic
  sentence-by-sentence generation, use a small persistent Python service around
  `OmniVoice.generate()`.
- Do not use voice cloning for impersonation, fraud, or other unauthorized
  purposes; follow the model's license, applicable law, and consent
  requirements.
