# Components, probe rules and dynamic pipelines

Contract shared by the runtime (`backend/pipelab/runtime`), the code
generators (`backend/pipelab/export`, Rust and Python are first class) and
the UI. Models: `components/models.py`, `graph/probes.py`, `graph/dynamic.py`.

## 1. Components (macro blocks)

A component is a reusable sub-graph stored in a **global library**
(`/data/components/<id>.json`). Instances are **linked**: editing the
component changes every instance (they reference it by id). "Expand" turns
one instance into plain elements in its parent graph (the way to get an
independent copy).

* `Component = {id (slug), name, description, version, graph, ports[], parameters[]}`.
* `ports[] = {name, direction: src|sink, node_id, pad}` expose inner pads.
  `pad` may be an always pad, a request template (requested when the
  instance is built) or a sometimes template (the port appears when the
  inner pad appears).
* `parameters[] = {name, description, default, targets[{node_id, property, pad?}]}`
  set inner (pad) properties. `default = null` keeps the inner value.
* Component graphs may contain probes, scripts and instances of other
  components (no cycles). They have no slots or functions.
* **Instance node**: a normal `Node` with `factory = "component:<id>"`;
  `properties` hold parameter values; edges use port names as pad names.
* **Catalog overlay**: every component is also an `ElementInfo` named
  `component:<id>` (family `component`, category `component`, plus
  `source`/`sink` when it has no sink/src ports): pads = ports (presence
  `sometimes` when the inner pad is a sometimes pad, else `always`; caps =
  effective caps of the inner pad), properties = parameters (typed like their
  first target property). Validation, link checks, layout and the palette
  therefore treat instances like elements.
* **Runtime / export**: an instance is a `GstBin` named after the node, with
  the inner elements (same names) and one ghost pad per port. Inner ids in
  runtime events are prefixed with the instance node id: `"<node>/<inner>"`
  (nested: `"a/b/c"`).
* API: `GET /api/components`, `POST /api/components/validate {component}` →
  `{issues}`, `GET|PUT|DELETE /api/components/{id}` (PUT
  creates or updates, bumping `version`), `GET /api/components/{id}/usage` →
  `{components[], projects[]}` (what references it directly, shown before deleting),
  `GET /api/components/starters` → `[{id, name, description, available, missing}]`
  and `POST /api/components/starters/{id}` (copies a starter into the library,
  409 if the id exists; definitions in `components/starters.py`),
  `GET /api/components/{id}/bundle` → `{format: "pipelab-components", version: 1,
  components[]}` (nested components first) and `POST /api/components/import
  {bundle, overwrite}` → `{imported[]}` (409 listing existing ids unless `overwrite`), `POST /api/components/from-selection
  {graph, node_ids, id, name}` → `{component, graph}` (selected nodes become
  the component; edges crossing the selection become ports; the returned
  graph has an instance in their place, re-linked), `POST /api/graph/expand
  {graph, node_id}` → `{graph}`.

## 2. Slots: N instances of a component

`Slot = {id, name, item, component, links[], initial[], max_instances, position?}`
(`position = {x, y}` is only where the editor draws the slot).

* `links[] = {port, node_id, pad, pad_properties}` connect a port of **every**
  instance to a pad of the static graph — normally a request template
  (`compositor.sink_%u`, `tee.src_%u`). For a `src` port the link goes
  instance → pad, for a `sink` port pad → instance.
  `pad_properties` values may use `$index` (instance number) and `$id`.
* `initial[] = {id, params}` instances are built before PLAYING (the
  configuration "before starting"). Instance ids are `<item><n>` with the
  smallest free `n` unless given.
* Runtime ids inside a slot instance are prefixed `"<slot id>.<instance id>/"`
  and the stats of its links use `"<slot id>.<instance id>:<port>"`.
* Built-in functions per slot: `add_<item>(**params, id=None) -> id`,
  `remove_<item>(id)`, `restart_<item>(id)` (remove + add with the same id
  and params), `list_<name>() -> [{id, params}]`.
* **Adding while running**: build the bin, add it to the pipeline, request /
  get the peer pads, apply pad properties, link, `sync_state_with_parent()`.
* **Removing while running**:
  * instances with only `src` links (sources such as an RTSP input):
    set the bin to NULL (its threads stop), unlink, release the request pads
    of the peers, remove the bin;
  * instances with `sink` links (consumers such as a recorder): block the
    upstream pad with an IDLE probe and unlink, send EOS into the instance
    and wait (≤ 3 s) for EOS to reach its sinks (pipeline `message-forward`),
    then NULL, release the request pads and remove.

## 3. Pipeline API functions

`ApiFunction = {name, description, params[{name, type, default}], actions[]}`
— methods of the pipeline for the software owning it. Actions use the same
vocabulary as probe rules (§4); `$<param>` references an argument.
Runtime: `POST /api/projects/{id}/runtime/call {function, args}` →
`{ok, result, error}` works for custom and built-in slot functions;
`GET /api/projects/{id}/runtime/instances` → `{slots: {<slot id>: [{id, params}]}}`
and a WS event `{"type": "instances", "slot", "instances": [...]}` on changes.

## 4. Probe rules (no code)

`ProbeRuleSet = {id, name, enabled, target{kind: node|edge, id, pad?}, variables{}, rules[]}`
and `ProbeRule = {id, when: Trigger, conditions[], actions[]}`.

* Watched pads: edge → the link's source pad; node → `target.pad` (name or
  template) or, if null, all its sink pads.
* Rule sets inside a component apply to every instance; `$instance` is the
  instance node name (or `""`).

### Triggers (`when`)
| type | fields | fires |
| --- | --- | --- |
| `start` | — | once when the pipeline first reaches PLAYING |
| `buffer` | — | every buffer (buffer lists: per buffer) |
| `event` | `event` (nick or `any`) | every matching downstream event |
| `idle` | `ms` | once when no buffer crossed the watched pads for `ms` (counted from PLAYING); re-armed by the next buffer |
| `resumed` | — | first buffer after an `idle` fired |
| `interval` | `ms` | periodically while running |
| `property` | `property` | a live change of that property was requested (UI, `set-property` from outside); node targets only |
| `signal` | `name` | `POST /runtime/signal {probe, name, value}` or a `signal` action |

### Conditions (`conditions`, all must hold; `negate` inverts one)
`keyframe` (no `delta-unit` flag) · `flag {flag}` (buffer flag nick) ·
`size {op, value}` (bytes) · `pts-gap {op, value}` (ms between consecutive
PTS) · `pts-backwards` · `every {n}` (every n-th evaluation of this rule) ·
`rate {op, value}` (buffers/s over the last second) · `caps-field {field, op,
value}` (current caps of the pad) · `variable {name, op, value}` · `pad {op,
value}` (pad name) · `random {percent}`.

### Actions (`actions`, executed in order)
| type | fields | effect |
| --- | --- | --- |
| `pass` / `drop` | — | verdict for the buffer/event (last one wins, default pass) |
| `block` / `unblock` | — | hold / release the data flow on the watched pad |
| `remove-probe` | — | disable this rule set |
| `post-message` | `name`, `fields` | application message on the bus (structure `name`) |
| `set-property` | `node`, `property`, `value`, `pad?` | like gst-launch; GstPad properties take a pad name |
| `send-event` | `event` (eos, flush, force-key-unit, custom), `direction`, `pad?`, `name?`, `fields?` | push an event |
| `request-keyframe` | `pad?` | upstream force-key-unit |
| `set-variable` / `increment` | `name`, `value` / `by` | probe variables |
| `log` | `message` (`{var}` placeholders), `level` | probe log (UI Probe tab) |
| `signal` | `probe?`, `name`, `value` | fire `signal` rules |
| `call` | `function`, `args` | call a pipeline function (§3) |
| `add-instance` / `remove-instance` / `restart-instance` | `slot`, `params` / `instance` | slot operations |

* Verdict for `property` triggers: a matching rule **intercepts** the change
  (it is not applied) unless it executes `pass`.
* Values: JSON primitives; `"$name"` references a variable or a builtin
  (`$value` trigger value, `$pad`, `$pts` s, `$size`, `$time` s since start,
  `$instance`, `$node`, `$idle_ms`, function `$<param>`); `"$$x"` is the
  literal `"$x"`.
* Threads: data triggers run in streaming threads; `call`, slot operations and
  `remove-probe` are deferred to the main loop. Variables are per rule set
  (per instance) and protected by a lock.
* Runtime events: `{"type": "probe-log", "probe", "level", "message", "time"}`;
  application messages appear as bus events `kind: "application"` with
  `name` and `fields`.
* `GET /api/probes/schema` describes triggers, conditions and actions with
  their fields for form-based editors.

## 5. Exported code

Rust (gstreamer-rs) and Python generate a **library** for the owning
software, not only a demo program:

* one builder per component returning a `Bin` with its ghost pads:
  Python `build_<component>(name, host=None, **params)`, Rust
  `build_<component>(name, &<Component>Params, &ProbeHost) -> Result<gst::Bin>`;
* a pipeline type `<Name>Pipeline`:
  * Python `<Name>Pipeline(config: dict | None)` where `config[<slot name>]`
    is a list of `{id?, **params}` replacing the slot's `initial` instances;
    Rust `<Name>Pipeline::new(Config)` with one `Vec<<Component>Params>` per
    slot (`Config::default()` = the `initial` instances);
  * `start()`, `stop()`, `send_eos()`, `set_element_property()`,
    `signal(probe, name, value)`, `element(path)` and `run()` (a GLib main
    loop for standalone use; Python turns SIGINT into EOS, Rust does not
    handle Ctrl+C);
  * application messages: Python `on_message(callback)`, Rust
    `connect_message(|message: &AppMessage| ...)`;
  * one method per API function (typed arguments) and per built-in slot
    function (`add_<item>`, `remove_<item>`, `restart_<item>`,
    `list_<name>`); Rust also has `call(function, args)` for rule actions;
* the Rust export targets gstreamer-rs 0.25 (`gstreamer`, `gstreamer-video`,
  `anyhow`; listed at the top of the file); `make test-rust` compiles and runs
  the export scenarios;
* every probe rule set as explicit code (a state struct guarded by a mutex,
  one branch per rule; idle/interval rules use GLib timeouts);
* scripts (Python) are embedded in the Python export and become porting
  notes in Rust.
