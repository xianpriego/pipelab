# Pipelab

Prototype GStreamer pipelines visually, run them with live previews and diagnostics, and export
the result as code for your application.

![Pipelab running an input-selector pipeline](docs/manual/images/running.png)

- **Every element of the machine.** GStreamer 1.28 with core, base, good, bad, ugly, libav, the
  Rust plugins, VA-API, QSV and NVIDIA `nvcodec` (NVDEC/NVENC and the CUDA filters), introspected
  live: around 1,500 elements, with every property typed and editable.
- **Links checked before they exist.** Caps are propagated through the graph. Incompatible
  links are refused with the elements that would bridge them, and the validator flags missing
  queues, parsers and converters, preroll deadlocks and invalid properties, with one-click
  fixes.
- **Run and inspect.**
  - Play, pause and stop; browser previews for video and audio sinks.
  - Bus messages that point at the failing element, with hints.
  - Live property changes, and input-selector switching on the node itself.
  - Watch or probe any link; the real runtime graph.
- **Performance.** Time per buffer in each element, queue fill levels and streaming threads
  with their CPU. Links can be coloured by thread, and bottlenecks are flagged.
- **Components.** Group elements into reusable blocks with ports and parameters, start from a
  starter library (RTSP inputs, encoders, recorders, network outputs), and share them as files.
- **Export.** gst-launch-1.0, Python (PyGObject), C, Rust (gstreamer-rs) or JSON. The Python and
  Rust exports are small libraries: one builder per component and a type that owns the
  pipeline.

## Quick start

Requirements: Docker with Compose v2. For NVIDIA elements, you also need the NVIDIA driver and the
NVIDIA Container Toolkit.

```bash
make up          # build and start on http://localhost:8080
make up GPU=1    # the same, with NVIDIA GPU access
make logs        # follow the logs
make down        # stop
```

Your projects, components, media files and the element catalog cache live in `./data`, on your
machine only (it is git-ignored). Relative file names in pipelines resolve inside `data/media`.
To receive RTP, RTSP or SRT streams from other machines, publish the ports in
`docker-compose.devices.yml` and start with `make up DEVICES=1`.

## Documentation

- [User manual](docs/manual/README.md): the interface, step by step, with screenshots.
- [Architecture](docs/ARCHITECTURE.md): modules, data model, HTTP API and runtime protocol.
- [Development](docs/DEVELOPMENT.md): running the tests, the dev mode and how to extend
  Pipelab.

The HTTP API is also described by OpenAPI at `http://localhost:8080/api/docs`.

## Known limitations

- There is no display or sound card inside Docker, so display and audio sinks are previewed in
  the browser. You can turn this off per sink.
- Object-typed properties (for example `playbin.video-sink`) cannot be set as text, just as in
  `gst-launch-1.0`.
- Properties without a mutability flag can be *tried* while playing. If the element ignores the
  change, the value read back shows it.
- NVIDIA elements depend on the GPU: an element appears only if the card supports it, for
  example AV1 needs an RTX 30 series or newer.
