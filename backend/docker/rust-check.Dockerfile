# syntax=docker/dockerfile:1.7
#
# Test image that compiles and runs the Rust code exported by Pipelab.
# It extends the API image (same GStreamer, headers and .pc files) with the
# Rust toolchain from the same pinned Arch snapshot.
#   make test-rust
ARG BASE_IMAGE=pipelab-api
FROM ${BASE_IMAGE}

RUN pacman -S --noconfirm --needed rust \
    && pacman -Scc --noconfirm \
    && rm -rf /var/cache/pacman/pkg/*

# Registry and build artefacts live in a named volume (see docker-compose.yml)
# so crates are downloaded and compiled only once.
ENV CARGO_HOME=/cargo \
    CARGO_TARGET_DIR=/cargo/target \
    PIPELAB_RUST_CHECK=1
RUN mkdir -p /cargo/target && chmod -R 777 /cargo
VOLUME ["/cargo"]
