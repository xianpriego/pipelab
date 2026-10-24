# Pipelab architecture

This document is the contract between Pipelab's modules: the processes, the data model, the
HTTP API and the runtime protocol. For how to run the tests and extend Pipelab, see
[DEVELOPMENT.md](DEVELOPMENT.md).

## Processes

```
browser (React + React Flow)
   │  HTTP /api/*      WebSocket /api/projects/{id}/runtime/ws
   ▼
web (nginx: static SPA + reverse proxy)                       container "web"
   ▼
api (FastAPI + PyGObject)                                     container "api"
   ├── catalog      introspects every element of the GStreamer registry
   ├── graph        model, caps flow, link checks, validation rules, fixes, layout
   ├── components   component library: overlay on the catalog, grouping, starters, files
   ├── importer     gst-launch-1.0 description → graph
   ├── export       gst-launch / Python / C / Rust / JSON generators
   ├── storage      projects, components and media under /data
   ├── runtime      one worker *process* per running project
   │      └── worker   builds the Gst.Pipeline and streams bus messages, statistics,
   │                   previews and probes back through a framed stdout protocol
   └── monitor      read-only reconstruction of *other* processes' live pipelines
```

A pipeline never runs inside the API process, so a crashing plugin only kills its worker. The
API process uses GStreamer only for introspection and caps arithmetic.

Data on disk (`/data`, the host's `./data`): `projects/<id>.json`, `components/<id>.json`,
`media/` (inputs and outputs of pipelines) and `cache/catalog-<registry hash>.json`.

## Graph model (`backend/pipelab/graph/models.py`)

```jsonc
{
  "nodes": [{
    "id": "n1",                       // stable internal id
    "factory": "videotestsrc",        // or "component:<id>" for a component instance
    "name": "src",                    // GStreamer element name, unique in the graph
    "properties": {"pattern": "ball", "is-live": true},   // non-default values only
    "pad_properties": {"sink_0": {"xpos": 10}},           // properties of request pads
    "position": {"x": 0, "y": 0},
    "preview": "auto"                 // "auto" | "off": replace display sinks by browser previews
  }],
  "edges": [{
    "id": "e1",
    "source": "n1", "source_pad": "src",       // concrete pad, or a *sometimes* template ("video_%u")
    "target": "n2", "target_pad": "sink"       // concrete pad ("sink_0" for request pads)
  }]
}
```

Property values are JSON primitives (`str | int | float | bool`) and follow the textual
conventions of `gst-launch-1.0`:

- enum nicks (`"ball"`);
- flags joined with `+`;
- caps strings;
- fractions (`"30/1"`);
- for `GstPad`-typed properties such as `input-selector::active-pad`, the pad name (`"sink_1"`).

Values are applied with `Gst.util_set_object_arg`, as `gst-launch-1.0` does, so exports and the
runtime behave identically.

Request pads: the frontend connects to a template handle (`sink_%u`), and the link check
resolves the next free concrete name (`sink_2`). Sometimes pads keep their template name and are
linked by the runtime on `pad-added`, to the first pad of that template whose caps fit the
target.

A project is `{id, name, description, created_at, updated_at, graph, settings: {gst_debug}}`
(`storage/models.py`). Unknown keys in stored documents are ignored, so older projects still load.

## Catalog (`backend/pipelab/catalog/`)

`build.py` supervises a subprocess (`python -m pipelab.catalog.describe_worker`) that
instantiates every element factory. If an element crashes or hangs the subprocess, it is
restarted past that element and the element is recorded as skipped. The result is cached by
registry hash. The registry itself is rebuilt at every container start, because `nvcodec`
registers different elements depending on the GPU.

- `ElementSummary`: `name, long_name, klass, description, rank, plugin, family, categories[],
  pads[]` (`{name, direction, presence, media_types[]}`), `selectors[]`, `preview`.
  `family` is one of `core | base | good | bad | ugly | libav | rs | component | other`.
- `ElementInfo`: the summary plus `author, package, origin, hierarchy[], interfaces[],
  uri_protocols[], pad_templates[]` (with full caps and pad properties) and `properties[]`.
- `PropertyInfo`: `name, nick, blurb, type, value_type, default, minimum, maximum,
  enum_values[], readable, writable, construct_only, mutable, controllable`.
  - `mutable` is one of `null | ready | paused | playing | unknown`.
  - `type` is one of `boolean int uint int64 uint64 float double string enum flags caps
    fraction structure pad object boxed array other`.

## Validation (`backend/pipelab/graph/`)

- `caps_flow.py` propagates *effective caps* through the graph:
  - it starts from the template caps;
  - narrows them with `caps` properties (capsfilter, appsrc, udpsrc…);
  - passes them through caps-agnostic elements (queue, tee, identity, valve…).
- `link_check.py` decides whether a proposed edge is allowed. Incompatible caps are refused, and
  `bridge.py` searches the catalog for chains of one or two elements that convert between both
  sides (videoconvert, parsers, decoders, encoders, cudadownload…). Links that are compatible
  but risky are accepted with a "for safety" suggestion.
- `rules/` has one function per rule:
  - missing or duplicate elements, invalid or required properties;
  - unlinked pads, no source or sink, incompatible links;
  - tee or demuxer branches without a queue, aggregator inputs, live sources;
  - source caps, encoder latency, payloader configuration, muxer finalisation, loopback preroll.
- `fixes.py` applies a machine-readable `Fix` (`insert_on_edge`, `connect_via`, `set_property`,
  `insert_tee`, `insert_after`) on the server; the client just replaces its graph.

```jsonc
// Issue
{"id": "tee-queue:n4:e7", "rule": "tee-queue", "severity": "warning",
 "message": "...", "node_ids": ["n4"], "edge_ids": ["e7"],
 "suggestions": [{"title": "Insert queue", "description": "...",
                  "fix": {"kind": "insert_on_edge", "edge_id": "e7",
                          "elements": [{"factory": "queue", "properties": {}}]}}]}
```

## Components (`backend/pipelab/components/`)

A component is a reusable sub-graph in a global library (`/data/components/<id>.json`):

```jsonc
{"id": "rtsp-input", "name": "RTSP input", "description": "", "version": 3, "updated_at": "...",
 "graph": {...},
 "ports": [{"name": "src", "direction": "src", "node_id": "out", "pad": "src"}],
 "parameters": [{"name": "location", "description": "", "default": null,
                 "targets": [{"node_id": "src", "property": "location", "pad": null}]}]}
```

- **Ports** expose inner pads: always pads, request templates (requested when the instance is
  built) or sometimes templates (the port appears with the inner pad).
- **Parameters** drive one or more inner (pad) properties. A `null` default keeps the inner
  value.
- **Instances** are nodes with `factory: "component:<id>"`. Their `properties` hold parameter
  values, and their edges use port names as pad names. Instances are *linked*: saving the
  component changes every instance. Expanding one (`POST /graph/expand`) turns it into a plain,
  independent copy of its elements.
- **Catalog overlay** (`overlay.py`): every component is also an `ElementInfo` named
  `component:<id>`, so validation, link checks, layout, the palette and the exports treat
  instances like elements:
  - pads are the ports, with the effective caps of the inner pads;
  - properties are the parameters, typed like their first target.
- **Runtime and exports:** an instance is a `GstBin` named after the node, holding the inner
  elements and one ghost pad per port. Ids of inner elements in runtime events are prefixed with
  the instance path: `"<instance>/<inner>"`, and `"a/b/c"` when nested.
- **Starters** (`starters.py`) are gst-launch descriptions with ports and parameters, resolved
  against the catalog of the machine and copied into the library on request.
- **Bundles** (`bundle.py`), the files used to share components:
  `{format: "pipelab-components", version: 1, components[]}`, with nested components first.

## HTTP API (prefix `/api`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | versions and catalog build state |
| GET | `/catalog` | `{elements: ElementSummary[]}` (components included) |
| GET | `/catalog/{factory}` | `ElementInfo` |
| GET | `/templates` | starter pipelines available on this machine |
| GET, POST | `/projects` | list / create (`{name, description?, template?, graph?}`) |
| GET, PUT, DELETE | `/projects/{id}` | read / update / delete (deleting also discards its runtime session) |
| POST | `/projects/{id}/duplicate` | copy a project |
| POST | `/graph/check-link` | `{graph, edge}` → `LinkCheckResult` |
| POST | `/graph/validate` | `{graph}` → `{issues: Issue[]}` |
| POST | `/graph/apply-fix` | `{graph, fix}` → `{graph}` |
| POST | `/graph/layout` | `{graph}` → `{graph}` with positions |
| POST | `/graph/expand` | `{graph, node_id}` → `{graph}` with the instance expanded |
| GET | `/components` | the library |
| GET, PUT, DELETE | `/components/{id}` | read / create or update (bumps `version`) / delete |
| POST | `/components/validate` | `{component}` → `{issues}` (no source/sink rules; ports may stay unlinked) |
| GET | `/components/{id}/usage` | `{components[], projects[]}` that reference it |
| POST | `/components/from-selection` | `{graph, node_ids, id, name}` → `{component, graph}` |
| GET | `/components/starters` | `[{id, name, description, available, missing[]}]` |
| POST | `/components/starters/{id}` | copy a starter into the library (409 if the id exists) |
| GET | `/components/{id}/bundle` | the component and the ones it contains, as a file |
| POST | `/components/import` | `{bundle, overwrite?}` → `{imported[]}` (409 lists existing ids) |
| GET | `/export/formats` | `[{id, label, language, extension, description}]` |
| POST | `/export` | `{graph, format, name}` → `{filename, language, content}` |
| POST | `/import/gst-launch` | `{description}` → `{graph, warnings[]}` |
| POST | `/projects/{id}/runtime/start` | spawn a worker and play (`{graph?, gst_debug?}`: unsaved edits) |
| POST | `/projects/{id}/runtime/play`, `/pause` | state changes |
| POST | `/projects/{id}/runtime/stop` | `{mode: "eos" \| "kill"}` |
| POST | `/projects/{id}/runtime/property` | `{node_id, property, value, pad?}` live change |
| GET | `/projects/{id}/runtime/properties/{node_id}` | values read from the live element (ids may contain `/`) |
| POST | `/projects/{id}/runtime/tap` | `{edge_id, enabled}`: preview what flows through a link |
| POST | `/projects/{id}/runtime/probe` | `{edge_id, enabled}`: list buffers and events of a link |
| GET | `/projects/{id}/runtime/dot` | SVG of the real running pipeline |
| GET | `/projects/{id}/runtime/status` | `RuntimeStatus` |
| WS | `/projects/{id}/runtime/ws` | runtime events and binary previews (closed with 4404 for unknown projects) |
| GET, POST | `/media` | list / upload (multipart `file`) |
| GET, DELETE | `/media/{path}` | serve (with HTTP range support) / delete |
| GET | `/monitor/processes` | `{processes: MonitorProcess[]}` — GStreamer processes visible to the API |
| POST | `/monitor/snapshot` | `{pid, method}` → `MonitorPipeline` (read-only reconstruction) |
| GET | `/monitor/live?pid=` | live `stats` over the interval since the last call, or `{available: false, reason}` |

Response details:

- `GET /health` → `{status: "ok", gstreamer_version, catalog: {state: "idle|building|ready|error",
  done, total, count, error}}`. Endpoints that need the catalog answer **503** while it is being
  built.
- `LinkCheckResult` = `{allowed, severity: ok|info|warning|error, edge (with resolved pad names),
  source_caps, target_caps, common_caps, issues: Issue[]}`.
- `RuntimeStatus` = `{project_id, state: idle|starting|ready|paused|playing|stopping|stopped|error,
  started_at, error}`. Every runtime POST returns it too.
- `POST /runtime/property` → `{ok, value?, error?}`. `value` is the value really in effect, and the
  change is validated against the graph that is running.

## Runtime protocol

API ⇄ worker: commands are JSON lines on the worker's stdin. Events are frames on its stdout:
`u32 header_len | u32 payload_len | header (JSON) | payload`. The worker's stderr (`GST_DEBUG`
output) is forwarded as `log` events, throttled. The session keeps the last events, so a
WebSocket that connects late receives the current state first.

Events, which are also what the WebSocket sends as JSON text frames:

```jsonc
{"type": "state", "state": "starting|ready|paused|playing|stopping|stopped|error", "error": null}
{"type": "bus", "kind": "error|warning|info|eos|state-changed|qos|element|tag|latency|stream-start|buffering|other",
 "source": "enc", "node_id": "n3", "text": "...", "debug": "...", "hint": "...", "fields": {...}, "time": 1.25}
{"type": "stats", "time": 3.0, "position": 2.9, "duration": null,
 "edges": {"e1": {"buffers": 90, "bytes": 1234, "fps": 30.0, "bitrate": 9000.0, "pts": 2.9}},
 // time spent inside each element over the last second: a buffer's PTS leaving it matched with
 // the same PTS entering it (elements that rewrite timestamps are absent)
 "elements": {"n2": {"avg_ms": 1.8, "max_ms": 4.2, "samples": 30}},
 // queue / queue2 levels; fill = fullest enabled limit (0..1); overruns = times it was full
 "queues": {"n3": {"buffers": 4, "bytes": 0, "time_ms": 133.3, "max_buffers": 200, "max_bytes": 10485760,
                   "max_time_ms": 1000.0, "fill": 0.133, "overruns": 0, "underruns": 1}},
 // streaming threads: native id, kernel name, CPU % over the last second (null on the first
 // report) and the links each one pushes
 "threads": [{"id": 4242, "name": "queue0:src", "cpu": 12.5, "edges": ["e3", "e4"]}]}
{"type": "caps", "edge_id": "e1", "caps": "video/x-raw, format=I420, ..."}
{"type": "property", "node_id": "n1", "property": "pattern", "value": "ball", "ok": true, "error": null}
{"type": "reply", "request_id": "...", "data": {...}}
{"type": "log", "line": "..."}
```

Selectors: `ElementSummary.selectors` lists the writable `GstPad`-typed properties, for example
`["active-pad"]` for `input-selector` and `output-selector`. When such a property changes inside
the running element, including the element's own automatic choice of the first pad, the worker
broadcasts:

```jsonc
{"type": "property", "node_id": "n4", "property": "active-pad", "value": "sink_1", "ok": true, "origin": "runtime"}
```

Probes: while a link is probed, batches of up to 100 items are broadcast every 250 ms:

```jsonc
{"type": "probe", "edge_id": "e3", "dropped": 0, "items": [
  {"kind": "buffer", "time": 1.52, "pts": 0.533, "dts": null, "duration": 0.033, "size": 34567,
   "flags": ["delta-unit"], "offset": null},
  {"kind": "event", "time": 1.50, "event": "caps", "detail": "video/x-raw, …"}]}
```

Previews are WebSocket binary frames `u32 header_len | header JSON | payload`:

- video: `{"kind": "video", "node_id", "mime": "image/jpeg", "width", "height"}`;
- audio: `{"kind": "audio", "node_id", "rate", "channels", "format": "F32LE"}`.

Previews of link taps use `node_id = "edge:<edge_id>"` and carry `edge_id`.

Display sinks (autovideosink, xvimagesink, glimagesink…) are replaced by an unconstrained
`appsink` that hands samples to a separate encoder pipeline, which produces JPEG frames limited
to 15 fps. Audio sinks are replaced by a PCM `appsink`. The element keeps its name, so bus
messages still map to the node, and since the replacement accepts any caps, upstream
negotiation does not change.

## Live monitor (`backend/pipelab/monitor/`)

Reconstructs, read-only, the pipeline running inside *another* process on the machine — a
command-line `gst-launch`, or an app written in C, Rust or Python, possibly in another container —
so it can be inspected as a graph. It never modifies the observed pipeline.

- `discover.py` scans `/proc` for processes with `libgstreamer-1.0.so` mapped and reports each one's
  command line, container (from `cgroup`), owner, and whether it was started with
  `GST_DEBUG_DUMP_DOT_DIR`. Only processes in the API's PID namespace are visible, so to monitor the
  whole host the API is run with `--pid=host` and `/proc` (and `CAP_SYS_PTRACE` for the gdb method).
- `dump.py` obtains a GraphViz `.dot` of the live pipeline by one of two methods:
  - **dot-dir** — read the newest dump the process has already written to its
    `GST_DEBUG_DUMP_DOT_DIR`. The directory is resolved through `/proc/<pid>/root`, so dumps inside
    another container are reachable. No cooperation beyond that one environment variable.
  - **gdb** (`gdb_dump.py`) — attach with gdb and call `gst_debug_bin_to_dot_data` (the same
    function GStreamer uses for the dumps) on every live top-level `GstPipeline`. The pipelines are
    found by taking the `GstPipeline` class pointer once and scanning the heap for instances that
    begin with it; only the few hits are validated and dumped. Needs ptrace permission. Matches
    plain `GstPipeline`/`gst-launch` pipelines, not custom `GstPipeline` subclasses.
- `dot_parse.py` parses the `.dot` back into elements (type, name, state, properties, bin nesting),
  pads (name and direction) and links (pad names and negotiated caps). It is pure and defensive.
- `graph_map.py` maps the parsed pipeline onto the read-only `monitor/models.py` models, resolving
  each element's GObject type to a factory against this machine's catalog (so the monitor reuses the
  editor's node rendering) and placing nodes with the editor's `auto_layout`.
- **Live statistics** (`live.py`, `tracer_parse.py`): when the process was launched with the
  GStreamer tracers (`GST_TRACERS="stats;latency"` + `GST_DEBUG=GST_TRACER:7` +
  `GST_DEBUG_FILE`), `discover.py` reports `full_stats`, and `LiveMonitor` tails that log (through
  `/proc/<pid>/root`). Each `/monitor/live` poll aggregates the records written since the previous
  poll into the same `stats` shape the editor streams — per-link `buffers/bytes/fps/bitrate`,
  per-element latency, end-to-end latency, and the streaming threads with their CPU (read from
  `/proc/<pid>/task/<tid>`). The poll interval is the measurement window. Tracers cannot be enabled
  after a process has started, so a pipeline that was not launched with them shows structure only.

`MonitorPipeline` = `{name, source, nodes: MonitorNode[], edges: MonitorEdge[]}`. A `MonitorNode` is
`{id, name, gtype, factory, factory_known, state, is_bin, parent, properties, position}` and a
`MonitorEdge` is `{id, source, source_pad, target, target_pad, caps}`. `source` describes where the
snapshot came from (`pid`, `cmdline`, `container`, `method`, `captured_at`).

## Frontend (`frontend/src`)

React 18 + TypeScript + Vite, `@xyflow/react` for the canvas, `zustand` for state, plain CSS with
design tokens (dark and light themes).

| Folder | Contents |
| --- | --- |
| `api/` | typed HTTP client and WebSocket |
| `pages/` | projects list and editor |
| `editor/` | the editor UI (see below) |
| `store/` | zustand stores (graph with undo, catalog, runtime, UI, components…) |
| `lib/` | pure, unit-tested logic: pads, search, scopes, performance… |

`editor/` holds:
- `canvas/`: nodes, edges, linking and the link toolbar;
- `palette/` and `inspector/`;
- `dock/`: issues, preview, bus, log, stats, performance, probe and outputs;
- `blocks/`: components;
- `dialogs/`.
