# Development

Everything runs in Docker; you do not need GStreamer, Python or Node on the host.

## Commands

```bash
make dev            # hot reload: API with uvicorn --reload, UI on http://localhost:5173
make test           # backend, frontend and browser suites, with linters
make test-backend   # ruff + pytest (real pipelines, every template, every export)
make test-frontend  # eslint + tsc + vitest + production build
make test-e2e       # Playwright/Chromium against the running stack (web + api)
make test-rust      # build and run the Rust exports with cargo (crates cached in a volume)
make test GPU=1     # the same with the GPU: NVIDIA and CUDA tests are skipped without one
make docs GPU=1     # regenerate the manual screenshots in docs/manual/images
make shell          # a shell in the api container
```

`make docs` starts a separate stack (`pipelab-docs`, port 8089) on an empty data folder, runs
`e2e/tests/docs.spec.ts` against it and removes it again, so your projects never appear in the
manual. Run it after any visible change to the interface.

## Repository layout

```
backend/                 FastAPI + PyGObject (Python 3.14) on Arch Linux, GStreamer 1.28
  pipelab/
    api/                 HTTP and WebSocket routers, shared services
    catalog/             element introspection (in a subprocess) and its cache
    graph/               data model, caps propagation, link checks, validation rules, fixes, layout
    components/          component library: models, catalog overlay, grouping, starters, files
    importer/            gst-launch-1.0 parser
    export/              gst-launch, Python, C, Rust and JSON exporters
    runtime/             one worker process per running pipeline, and its protocol
    storage/             projects, components and media on disk
    templates/           starter pipelines
  tests/                 pytest; runtime tests run real pipelines
frontend/                React 18 + TypeScript + Vite, @xyflow/react, zustand
  src/
    api/                 HTTP/WebSocket client and types
    editor/              canvas, palette, inspector, dock, components (blocks/), dialogs
    lib/                 pure helpers, unit-tested
    store/               zustand stores
e2e/                     Playwright suite (and the manual screenshots)
docs/                    architecture, this guide and the user manual
```

[ARCHITECTURE.md](ARCHITECTURE.md) describes how the pieces talk to each other.

## Tests

- Backend tests use the real element catalog of the container and run real pipelines. Every
  template is validated and started, and data must flow on all of its links. The exports are
  checked too: the Python code runs, the C code compiles, and cargo builds and runs the Rust
  code (`make test-rust`).
- Frontend unit tests cover the pure logic in `lib/`, the stores and the main components.
- The browser suite drives the real interface: templates, running with previews, live changes,
  refused links with bridges, runtime errors, outputs, probes, performance, components, starters
  and export/import.

To try changes without touching your own stack on port 8080, run a second one with its own data.
This is the same mechanism `make docs` uses:

```bash
PIPELAB_DATA=./.staging/data PIPELAB_PORT=8081 docker compose -p pipelab-staging up -d --build
```

## Extending Pipelab

- **A validation rule:** write a function `(RuleContext) -> list[Issue]` in one of the modules
  of `backend/pipelab/graph/rules/` and add it to `RULES` in `rules/__init__.py`. Use
  `rules/base.issue()` to build issues. A `Fix` attached to a suggestion becomes a one-click
  button in the UI.
- **A template:** add a `Starter` (a gst-launch description) to
  `backend/pipelab/templates/starters.py`. The template test runs it and checks data on every
  link.
- **A starter component:** add a `StarterComponent` to `backend/pipelab/components/starters.py`.
  It needs a gst-launch description with `name=` on the elements its ports and parameters refer
  to.
- **A fix kind:** add the literal to `FixKind` (`graph/models.py`) and a handler in
  `graph/fixes.py`, then mirror the type in `frontend/src/api/types.ts`.
- **A browser preview for another sink:** add the factory to `VIDEO_SINKS` / `AUDIO_SINKS` in
  `backend/pipelab/catalog/previewable.py`.
- **An export format:** add an `ExportFormat` and a renderer to `backend/pipelab/export/__init__.py`.
- **Upgrading GStreamer:** bump `ARCH_SNAPSHOT` in `backend/Dockerfile`. The registry is
  rebuilt at every start, and the catalog cache is keyed by its hash.

## Conventions

- Small modules with one responsibility, docstrings that say why, and no dead code.
- Python: ruff (lint and format, line length 110). TypeScript: eslint and `tsc --strict`.
- Commits end with the tests green: `make test` (add `GPU=1` on a GPU machine).
