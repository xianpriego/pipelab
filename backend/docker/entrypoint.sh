#!/bin/sh
# The GStreamer registry is rebuilt on every start: plugins such as nvcodec
# register different elements depending on the hardware visible to the
# container, so a registry cached at build time would hide them.
set -e
rm -f "${GST_REGISTRY:-/tmp/gstreamer-registry.bin}"
mkdir -p "${PIPELAB_DATA_DIR:-/data}"
exec "$@"
