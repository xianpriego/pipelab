# Pipelab architecture

Pipelab is a web tool to prototype GStreamer pipelines graphically. This
document is the contract between its modules.

## Components

```
browser (React + React Flow)
   │  HTTP /api/*   WebSocket /api/projects/{id}/runtime/ws
   ▼
web (nginx: static SPA + reverse proxy)          ── container "web"
   ▼
api (FastAPI, Python, PyGObject)                 ── container "api"
   ├── catalog     introspects every element in the GStreamer registry
   ├── graph       models, caps flow, link checks, validation rules, fixes, layout
   ├── export      gst-launch / Python / C / Rust / JSON generators
   ├── importer    gst-launch description parser → graph
   ├── storage     projects stored as JSON files in /data/projects
   └── runtime     one worker *process* per running project
          └── worker  builds the Gst.Pipeline, streams bus messages, stats and
                      previews back through a framed stdout protocol
```

A pipeline never runs inside the API process: a crashing plugin only kills its
worker. The API process only uses GStreamer for introspection and caps math.

## Graph model (`backend/pipelab/graph/models.py`)

```jsonc
{
  "nodes": [{
    "id": "n1",                      // stable internal id
    "factory": "videotestsrc",
    "name": "src",                   // GStreamer element name, unique in graph
    "properties": {"pattern": "ball", "is-live": true},   // non-default values only
    "pad_properties": {"sink_0": {"xpos": 10}},           // properties of request pads
    "position": {"x": 0, "y": 0},
    "preview": "auto"               // "auto" | "off" — replace display sinks by browser previews
  }],
  "edges": [{
    "id": "e1",
    "source": "n1", "source_pad": "src",       // concrete pad or a *sometimes* template ("video_%u")
    "target": "n2", "target_pad": "sink"       // concrete pad ("sink_0" for request pads)
  }]
}
```

Property values are JSON primitives (`str | int | float | bool`) using the same
textual conventions as `gst-launch-1.0`: enum nicks (`"ball"`), flags joined
with `+`, caps strings, fractions (`"30/1"`), and for `GstPad`-typed
properties (e.g. `input-selector::active-pad`) the pad name (`"sink_1"`).
Every value is applied with `Gst.util_set_object_arg`, exactly like
`gst-launch-1.0`, so exports and the runtime behave identically.

Request pads: the frontend connects to a template handle (`sink_%u`); the link
check resolves the next free concrete name (`sink_2`). Sometimes pads stay as
template names and are linked by the runtime on `pad-added` (first pad of that
template whose caps are compatible with the target).

A project is `{id, name, description, created_at, updated_at, graph, settings}`
with `settings = {gst_debug: "*:2"}`.

## Catalog model (`backend/pipelab/catalog/models.py`)

Built in a subprocess (`python -m pipelab.catalog.builder`) that instantiates
every element factory; crashes on a single element are survived by restarting
past it. Cached in `/data/cache/catalog-<registry-hash>.json`.

* `ElementSummary` — `name, long_name, klass, description, rank, plugin,
  family (core|base|good|bad|ugly|libav|rs|other), categories[], pads[]` where
  each pad is `{name, direction, presence, media_types[]}`.
* `ElementInfo` — summary + `author, package, origin, hierarchy[],
  interfaces[], uri_protocols[], pad_templates[] (with full caps and pad
  properties), properties[]`.
* `PropertyInfo` — `name, nick, blurb, type, value_type, default, minimum,
  maximum, enum_values[], readable, writable, construct_only, mutable
  (null|ready|paused|playing|unknown), controllable`. `type` is one of
  `boolean int uint int64 uint64 float double string enum flags caps fraction
  structure pad object boxed array other`.

## Validation (`backend/pipelab/graph/`)

* `caps_flow.py` propagates *effective caps* through the graph: template caps,
  narrowed by `caps` properties (capsfilter, appsrc, udpsrc…) and passed
  through caps-agnostic elements (queue, tee, identity, valve…).
* `link_check.py` decides if a proposed edge is allowed. Incompatible caps are
  rejected and `bridge.py` searches the catalog for 1–2 element chains that
  convert between both sides (videoconvert, h264parse, decoders, cudadownload…).
  Compatible-but-risky links (source caps not a subset of sink caps) are
  accepted with a "for safety" suggestion.
* `rules/` holds one module per graph rule (tee without queues, aggregator
  inputs without queues, demuxer outputs, missing parser, unlinked pads,
  required properties, cycles, live sources, encoder tuning…). Each returns
  `Issue`s with `Suggestion`s carrying a machine-applicable `Fix`.
* `fixes.py` applies a `Fix` to a graph (`insert_on_edge`, `connect_via`,
  `set_property`, `insert_tee`, `insert_after`) — fixes are computed
  server side and the client just replaces its graph.

```jsonc
// Issue
{"id": "tee-queue:n4:e7", "rule": "tee-queue", "severity": "warning",
 "message": "...", "node_ids": ["n4"], "edge_ids": ["e7"],
 "suggestions": [{"title": "Insert queue", "description": "...",
                  "fix": {"kind": "insert_on_edge", "edge_id": "e7",
                          "elements": [{"factory": "queue", "properties": {}}]}}]}
```

## HTTP API (prefix `/api`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | versions + catalog build state |
| GET | `/catalog` | `{elements: ElementSummary[]}` |
| GET | `/catalog/{factory}` | `ElementInfo` |
| GET/POST | `/projects` | list / create (`{name, description?, template?, graph?}`) |
| GET/PUT/DELETE | `/projects/{id}` | read / update / delete |
| POST | `/projects/{id}/duplicate` | copy a project |
| GET | `/templates` | starter pipelines available on this machine |
| POST | `/graph/check-link` | `{graph, edge}` → `LinkCheckResult` |
| POST | `/graph/validate` | `{graph}` → `{issues: Issue[]}` |
| POST | `/graph/apply-fix` | `{graph, fix}` → `{graph}` |
| POST | `/graph/layout` | `{graph}` → `{graph}` with positions |
| POST | `/export` | `{graph, format, name}` → `{filename, language, content}` |
| GET | `/export/formats` | available formats |
| POST | `/import/gst-launch` | `{description}` → `{graph, warnings[]}` |
| POST | `/projects/{id}/runtime/start` | spawn worker and play |
| POST | `/projects/{id}/runtime/{play,pause}` | state changes |
| POST | `/projects/{id}/runtime/stop` | `{mode: "eos" \| "kill"}` |
| POST | `/projects/{id}/runtime/property` | `{node_id, property, value, pad?}` live change |
| GET | `/projects/{id}/runtime/properties/{node_id}` | current values read from the live element |
| POST | `/projects/{id}/runtime/tap` | `{edge_id, enabled}` preview what flows through a link |
| GET | `/projects/{id}/runtime/dot` | SVG of the real running pipeline |
| GET | `/projects/{id}/runtime/status` | state, last error |
| WS | `/projects/{id}/runtime/ws` | runtime events + binary previews |
| GET/POST/DELETE | `/media[/{path}]` | files in `/data/media` (inputs and outputs) |

### Response shapes

* `GET /health` → `{status: "ok", gstreamer_version, catalog: {state: "idle|building|ready|error", done, total, count, error}}`.
  Catalog-dependent endpoints answer **503** while the catalog is building.
* `GET /projects` → `ProjectSummary[]` (`id, name, description, created_at, updated_at, node_count`).
* `Project` = `{id, name, description, created_at, updated_at, graph, settings: {gst_debug}}`
  (`backend/pipelab/storage/models.py`). `PUT` takes any subset of `name, description, graph, settings`.
* `GET /templates` → `[{id, name, description, available, missing: string[]}]`.
* `POST /graph/check-link` → `LinkCheckResult = {allowed, severity: ok|info|warning|error, edge
  (with resolved pad names), source_caps, target_caps, common_caps, issues: Issue[]}`.
* `GET /export/formats` → `[{id, label, language, extension, description}]`; ids:
  `gst-launch`, `python`, `c`, `rust`, `json`.
* `GET /projects/{id}/runtime/status` and every runtime POST → `RuntimeStatus =
  {project_id, state: idle|starting|ready|paused|playing|stopping|stopped|error, started_at, error}`.
  `start` accepts `{graph?, gst_debug?}` to run unsaved edits.
* `GET /projects/{id}/runtime/properties/{node_id}` → `{node_id, properties: {name: value}}`.
* `GET /projects/{id}/runtime/dot` → `image/svg+xml`.
* `POST /projects/{id}/runtime/property` → `{ok, value?, error?}` (value actually in effect);
  `POST /projects/{id}/runtime/tap` → `{ok, error?}`.
* `GET /media` → `{files: [{path, size, modified, mime}]}`; `POST /media` is multipart (`file`);
  `GET /media/{path}` serves the file with HTTP range support (video playback).

## Runtime protocol

API ⇄ worker: commands are JSON lines on the worker's stdin; events are frames
on its stdout: `u32 header_len | u32 payload_len | header (JSON) | payload`.
Worker stderr (GST_DEBUG output) is forwarded as `log` events.

Events (also what the WebSocket sends, JSON text frames):

```jsonc
{"type": "state", "state": "starting|ready|paused|playing|stopping|stopped|error"}
{"type": "bus", "kind": "error|warning|info|eos|state-changed|qos|element|tag|latency|stream-start|buffering|other",
 "source": "enc", "node_id": "n3", "text": "...", "debug": "...", "hint": "...", "fields": {...}, "time": 1.25}
{"type": "stats", "time": 3.0, "position": 2.9, "duration": null,
 "edges": {"e1": {"buffers": 90, "bytes": 1234, "fps": 30.0, "bitrate": 9000.0}},
 // time spent inside each element over the last second: a buffer's PTS leaving it matched with the
 // same PTS entering it (elements that rewrite timestamps are absent)
 "elements": {"n2": {"avg_ms": 1.8, "max_ms": 4.2, "samples": 30}},
 // queue / queue2 levels; fill = fullest enabled limit (0..1); overruns = times it was full (drops if leaky)
 "queues": {"n3": {"buffers": 4, "bytes": 0, "time_ms": 133.3, "max_buffers": 200, "max_bytes": 10485760,
                   "max_time_ms": 1000.0, "fill": 0.133, "overruns": 0, "underruns": 1}},
 // streaming threads (native id, kernel name such as "queue0:src"), CPU % over the last second
 // (null on the first report) and the links each one pushes
 "threads": [{"id": 4242, "name": "queue0:src", "cpu": 12.5, "edges": ["e3", "e4"]}]}
{"type": "caps", "edge_id": "e1", "caps": "video/x-raw, format=I420, ..."}
{"type": "property", "node_id": "n1", "property": "pattern", "value": "ball", "ok": true, "error": null}
{"type": "reply", "request_id": "...", "data": {...}}
{"type": "log", "line": "..."}
```

Selectors and probes:

```jsonc
// ElementSummary.selectors: writable GstPad-typed properties, e.g. ["active-pad"] for
// input-selector / output-selector. They choose among the element's *request* pads.
// When such a property changes inside the running element (including the automatic
// choice of the first pad) the worker broadcasts:
{"type": "property", "node_id": "n4", "property": "active-pad", "value": "sink_1", "ok": true, "origin": "runtime"}
// POST /projects/{id}/runtime/probe {edge_id, enabled} → {ok, error?} inspects a link;
// batches (≤ 100 items, every 250 ms) are broadcast as:
{"type": "probe", "edge_id": "e3", "dropped": 0, "items": [
  {"kind": "buffer", "time": 1.52, "pts": 0.533, "dts": null, "duration": 0.033, "size": 34567,
   "flags": ["delta-unit"], "offset": null},
  {"kind": "event", "time": 1.50, "event": "caps", "detail": "video/x-raw, …"}]}
```

### Probe scripts

`Graph.scripts` holds user Python attached to a link or an element:

```jsonc
{"id": "s1", "name": "Switch on keyframe", "enabled": true,
 "target": {"kind": "node", "id": "n4"},          // or {"kind": "edge", "id": "e3"}
 "code": "def on_property(ctx, name, value): ..."}
```

Callbacks (all optional, module level): `setup(ctx)`, `on_buffer(ctx, pad, buffer)`,
`on_event(ctx, pad, event)`, `on_property(ctx, name, value) -> bool` (node scripts:
intercepts a live property change requested from the UI), `on_trigger(ctx, value)`.
Watched pads: edge scripts → the link's source pad; node scripts → the element's sink
pads (`WATCH = "src"` or `"all"` changes it). Return `PASS` (default), `DROP` or
`REMOVE`. `ctx`: `element`, `pad`, `pipeline`, `state`, `get(name)`, `pad_named(name)`,
`log(message, **fields)`, `set(element_name, prop, value)`, `request_keyframe(pad=None)`,
`is_keyframe(buffer)`. `Gst` and `GLib` are importable/predefined.

* `GET /scripts/recipes` → `[{id, name, description, target_kind, factories[], code}]`.
* `POST /projects/{id}/runtime/trigger {script_id, value?}` → `{ok, error?}`.
* `POST /runtime/property` answers `{ok, deferred: true, value}` when a script took over.
* WS `{"type": "script", "script_id", "name", "level": "info|warning|error", "message", "time", "fields"?}`.
* Validation rule `script` reports syntax errors (with line), missing targets and scripts
  without callbacks.

Previews are WebSocket binary frames `u32 header_len | header JSON | payload`
with header `{"kind": "video", "node_id", "mime": "image/jpeg", "width", "height"}`
or `{"kind": "audio", "node_id", "rate", "channels", "format": "F32LE"}`.
Previews of link taps use `node_id = "edge:<edge_id>"` and carry `edge_id`.
Display sinks (autovideosink, xvimagesink, glimagesink…) are replaced by a JPEG
`appsink` branch and audio sinks by a PCM `appsink` branch; the element name is
kept so bus messages still map to the node.

## Frontend (`frontend/src`)

React 18 + TypeScript + Vite, `@xyflow/react` for the canvas, `zustand` for
state, plain CSS with design tokens. Folders: `api/` (typed client + websocket),
`pages/` (projects list, editor), `editor/` (canvas, nodes, palette,
inspector, issues, runtime panels, export/import dialogs), `store/`, `lib/`.

## Conventions

* Small modules with one responsibility; no file above ~300 lines.
* Backend: type hints everywhere, pydantic models at the boundaries, `ruff`.
* Tests live next to each package's concern in `backend/tests` and
  `frontend/src/**/*.test.ts(x)`; everything runs in Docker (`make test`).

## Extending

* **A validation rule**: write a function `(ctx: RuleContext) -> list[Issue]` in
  a module of `backend/pipelab/graph/rules/` (use `rules.base.issue` and the
  helpers in `graph/suggest.py` to attach fixes), register it in
  `rules/__init__.py` and add a test in `backend/tests/test_validate.py`.
* **A fix kind**: add the literal to `FixKind` (`graph/models.py`), a handler
  in `graph/fixes.py` and mirror the type in `frontend/src/api/types.ts`.
* **An export format**: add a generator module in `backend/pipelab/export/`
  built on `common.build_spec` and register it in `export/__init__.py`.
* **A starter template**: append a `Starter` with a gst-launch description to
  `backend/pipelab/templates/starters.py`; `tests/test_templates.py` will
  validate and run it automatically.
* **A preview for another sink**: add the factory to `VIDEO_SINKS` /
  `AUDIO_SINKS` in `backend/pipelab/catalog/previewable.py` (the catalog exposes it as `preview`).
