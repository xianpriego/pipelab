# syntax=docker/dockerfile:1.7
#
# Pipelab backend: FastAPI + PyGObject on top of the most complete GStreamer
# distribution we can get from packages (Arch Linux ships base/good/bad/ugly,
# libav, nvcodec, va, msdk/qsv and the whole gst-plugins-rs set).
#
# The package repositories are pinned to an Arch Linux Archive snapshot so the
# build is reproducible. Bump ARCH_SNAPSHOT to upgrade GStreamer.

ARG ARCH_IMAGE=archlinux:latest@sha256:e43f1fd80e073992c5f173efbbbf65144170bf60aeb7369940087d63eacea8f4

FROM ${ARCH_IMAGE} AS gstreamer

ARG ARCH_SNAPSHOT=2026/10/20

RUN echo "Server=https://archive.archlinux.org/repos/${ARCH_SNAPSHOT}/\$repo/os/\$arch" \
        > /etc/pacman.d/mirrorlist \
    && sed -i 's/^#\?ParallelDownloads.*/ParallelDownloads = 8/' /etc/pacman.conf \
    && pacman -Syyuu --noconfirm --needed \
        python python-gobject graphviz ttf-dejavu \
        gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad \
        gst-plugins-bad-libs gst-plugins-ugly gst-libav gst-rtsp-server \
        gst-python gst-editing-services \
        gst-plugin-va gst-plugin-msdk gst-plugin-qsv gst-plugin-hip \
        gst-plugin-onnx gst-plugin-opencv gst-plugin-gtk gst-plugin-qml6 \
        gst-plugin-qmlgl gst-plugin-wpe2 gst-plugin-libcamera \
        gst-plugin-pipewire gst-plugin-svthevcenc gst-plugins-espeak \
        gst-plugins-rs \
    && pacman -Scc --noconfirm \
    && rm -rf /var/cache/pacman/pkg/*

FROM gstreamer AS runtime

# Compilers let the test-suite check that exported C code really builds.
RUN pacman -S --noconfirm --needed gcc pkgconf \
    && pacman -Scc --noconfirm \
    && rm -rf /var/cache/pacman/pkg/*

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GST_REGISTRY=/tmp/gstreamer-registry.bin \
    NVIDIA_DRIVER_CAPABILITIES=all \
    PIPELAB_DATA_DIR=/data \
    PYTHONPATH=/app \
    HOME=/tmp \
    RUFF_CACHE_DIR=/tmp/.ruff_cache

# --system-site-packages exposes the distro PyGObject (gi) to the venv.
RUN python -m venv --system-site-packages ${VIRTUAL_ENV}

# NVRTC, NVIDIA's runtime compiler (~60 MB, not the whole CUDA toolkit): nvcodec
# compiles its CUDA kernels with it when it starts, otherwise cudaconvert,
# cudascale, cudaconvertscale and cudacompositor are not registered. Harmless
# without a GPU (nvcodec then registers nothing).
ARG NVRTC_VERSION=12.9.86
RUN pip install --no-cache-dir --target /opt/nvrtc nvidia-cuda-nvrtc-cu12==${NVRTC_VERSION}
ENV GST_CUDA_NVRTC_LIBNAME=/opt/nvrtc/nvidia/cuda_nvrtc/lib/libnvrtc.so.12 \
    LD_LIBRARY_PATH=/opt/nvrtc/nvidia/cuda_nvrtc/lib

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY pyproject.toml ./
COPY pipelab ./pipelab
COPY tests ./tests
COPY docker/entrypoint.sh /usr/local/bin/pipelab-entrypoint

EXPOSE 8000
VOLUME ["/data"]
ENTRYPOINT ["pipelab-entrypoint"]
CMD ["uvicorn", "pipelab.main:app", "--host", "0.0.0.0", "--port", "8000"]
