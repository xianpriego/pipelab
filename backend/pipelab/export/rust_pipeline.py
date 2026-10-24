"""The pipeline type of the Rust library: static graph, slots, API functions, bus, demo."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pipelab.export.plan import ProgramPlan, SlotPlan
from pipelab.export.rust_api import call_method, dispatch_method, function_method
from pipelab.export.rust_support_pipeline import LIFECYCLE, STATE
from pipelab.export.rust_syntax import rust_str, typed_literal, value_literal
from pipelab.graph.models import Graph

if TYPE_CHECKING:
    from pipelab.export.rust_dynamic import ScopeRenderer


def _config(program: ProgramPlan) -> list[str]:
    lines = ["", "/// Initial slot instances: `Config::default()` holds the ones defined in the editor."]
    if not program.slots:
        return [*lines, "#[derive(Clone, Debug, Default)]", "pub struct Config {}"]
    fields, defaults = [], []
    for slot in program.slots:
        title = slot.component.component.name
        fields += [
            f"    /// `{slot.slot.name}`: {title} instances.",
            f"    pub {slot.ident}: Vec<{slot.component.type_name}Params>,",
        ]
        entries = [_params_literal(slot, instance.params) for instance in slot.slot.initial]
        defaults.append(f"            {slot.ident}: vec![{', '.join(entries)}],")
    return [
        *lines,
        "#[derive(Clone, Debug)]",
        "pub struct Config {",
        *fields,
        "}",
        "",
        "impl Default for Config {",
        "    fn default() -> Self {",
        "        Config {",
        *defaults,
        "        }",
        "    }",
        "}",
    ]


def _params_literal(slot: SlotPlan, values: dict) -> str:
    name = f"{slot.component.type_name}Params"
    fields = []
    for param in slot.component.params:
        literal = typed_literal(param.kind, values.get(param.name)) if param.name in values else None
        if literal is not None:
            fields.append(f"{param.ident}: Some({literal})")
    if not fields:
        return f"{name}::default()"
    rest = ", ..Default::default()" if len(fields) < len(slot.component.params) else ""
    return f"{name} {{ {', '.join(fields)}{rest} }}"


def _slot_new(slot: SlotPlan, names: dict[str, str]) -> list[str]:
    ports = {p.name: p for p in slot.component.ports}
    lines = [
        f"{slot.ident}: rt::Slot::new(",
        f"    {rust_str(slot.slot.item)},",
        f"    build_{slot.component.ident},",
        "    vec![",
    ]
    for link in slot.slot.links:
        src = "true" if link.port not in ports or ports[link.port].direction == "src" else "false"
        properties = ", ".join(f"({rust_str(k)}, {value_literal(v)})" for k, v in link.pad_properties.items())
        lines += [
            "        rt::SlotLink {",
            f"            port: {rust_str(link.port)},",
            f"            src: {src},",
            f"            element: {rust_str(names.get(link.node_id, link.node_id))},",
            f"            pad: {rust_str(link.pad)},",
            f"            properties: vec![{properties}],",
            "        },",
        ]
    limit = f"Some({slot.slot.max_instances})" if slot.slot.max_instances is not None else "None"
    return [*lines, "    ],", f"    {limit},", "),"]


def _new(program: ProgramPlan, graph: Graph, renderer: ScopeRenderer) -> list[str]:
    names = {node.id: node.name for node in graph.nodes}
    root = program.root
    body = [
        "gst::init()?;",
        f"let pipeline = gst::Pipeline::builder().name({rust_str(program.name)}).build();",
    ]
    if program.message_forward:
        body.append('pipeline.set_property("message-forward", true); // EOS of draining slot instances')
    body.append("let host = ProbeHost::default();")
    if root.spec.elements:
        body += [
            "let container = pipeline.clone().upcast::<gst::Bin>();",
            "let mut elements = Elements::new();",
        ]
    else:
        body.append("let elements = Elements::new();")
    body += [*renderer.elements(root), *renderer.links(root), *renderer.probes(root, graph, False)]
    fields = ["pipeline", "elements", "host"]
    if program.slots:
        body += [
            "let slots = Slots {",
            *[f"    {line}" for s in program.slots for line in _slot_new(s, names)],
            "};",
        ]
        fields.append("slots: Mutex::new(slots)")
    fields += ["callbacks: Mutex::default()", "started: Mutex::default()", "watch: Mutex::default()"]
    fields += ["main_loop: Mutex::default()", "error: Mutex::default()"]
    cls = f"{program.type_name}Pipeline"
    body += [
        "let inner = Inner {",
        *[f"    {field}," for field in fields],
        "};",
        f"let this = {cls} {{ inner: Arc::new(inner) }};",
        "let weak = Arc::downgrade(&this.inner);",
        "this.inner.host.set_dispatcher(Box::new(move |job| {",
        "    if let Some(inner) = weak.upgrade() {",
        f"        if let Err(err) = ({cls} {{ inner }}).dispatch(job) {{",
        '            eprintln!("deferred action failed: {err:#}");',
        "        }",
        "    }",
        "}));",
    ]
    for slot in program.slots:
        ids = ", ".join(rust_str(i.id) for i in slot.slot.initial)
        body += [
            f"let ids: &[&str] = &[{ids}]; // editor ids of the initial instances",
            f"for (index, params) in config.{slot.ident}.into_iter().enumerate() {{",
            "    let (mut slots, scope) = this.slots();",
            f"    slots.{slot.ident}.add(&scope, params, ids.get(index).map(|id| id.to_string()))?;",
            "}",
        ]
    body.append("Ok(this)")
    config = "config" if program.slots else "_config"
    return [
        "    /// Builds the static graph, its probe rule sets and the initial slot instances.",
        f"    pub fn new({config}: Config) -> Result<Self> {{",
        *[f"        {line}" for line in body],
        "    }",
    ]


def _slot_methods(slot: SlotPlan) -> list[str]:
    params = f"{slot.component.type_name}Params"
    field, key = slot.ident, rust_str(slot.slot.id)
    drain = [
        f"    if slots.{field}.remove(&scope, id, RESTART)? {{",
        f"        self.finish_later({key}, id);",
        "    }",
    ]
    remove = drain if slot.has_sink_links else [f"    slots.{field}.remove(&scope, id, RESTART)?;"]
    lines = [
        "",
        f"/// Adds a {slot.component.component.name} to `{slot.slot.name}`; returns its id.",
        f"pub fn add_{slot.item}(&self, params: {params}) -> Result<String> {{",
        "    let (mut slots, scope) = self.slots();",
        f"    slots.{field}.add(&scope, params, None)",
        "}",
        "",
        f"/// Removes a `{slot.slot.name}` instance"
        + (" (it drains first, at most 3 s)." if slot.has_sink_links else "."),
        f"pub fn remove_{slot.item}(&self, id: &str) -> Result<()> {{",
        "    let (mut slots, scope) = self.slots();",
        *[line.replace("RESTART", "false") for line in remove],
        "    Ok(())",
        "}",
        "",
        f"/// Removes and adds again a `{slot.slot.name}` instance with the same id and parameters.",
        f"pub fn restart_{slot.item}(&self, id: &str) -> Result<String> {{",
        "    let (mut slots, scope) = self.slots();",
        *[line.replace("RESTART", "true") for line in remove],
        "    Ok(id.to_string())",
        "}",
        "",
        f"/// The `{slot.slot.name}` instances: (id, parameters).",
        f"pub fn list_{slot.ident}(&self) -> Vec<(String, {params})> {{",
        f"    self.slots().0.{field}.list()",
        "}",
    ]
    return lines


def _drain_methods(program: ProgramPlan) -> list[str]:
    """Completion of removals that drain (EOS forwarded by the pipeline, or a 3 s timeout)."""
    sinks = [s for s in program.slots if s.has_sink_links]
    if not sinks:
        return ["", "fn finish_drained(&self, _source: &gst::Object) {}"]
    cls = f"{program.type_name}Pipeline"
    arms = [f"    {rust_str(s.slot.id)} => slots.{s.ident}.finish(&scope, id)," for s in sinks]
    collect = [
        f"    let ids = slots.{s.ident}.drained(source);\n"
        f"        drained.extend(ids.into_iter().map(|id| ({rust_str(s.slot.id)}, id)));"
        for s in sinks
    ]
    return [
        "",
        "fn finish_later(&self, slot: &'static str, id: &str) {",
        "    let (weak, id) = (Arc::downgrade(&self.inner), id.to_string());",
        "    glib::timeout_add_once(Duration::from_secs(3), move || {",
        "        if let Some(inner) = weak.upgrade() {",
        f"            {cls} {{ inner }}.finish(slot, &id);",
        "        }",
        "    });",
        "}",
        "",
        "fn finish(&self, slot: &str, id: &str) {",
        "    let (mut slots, scope) = self.slots();",
        "    let result = match slot {",
        *[f"    {arm}" for arm in arms],
        "        _ => Ok(()),",
        "    };",
        "    if let Err(err) = result {",
        '        eprintln!("could not remove {id}: {err:#}");',
        "    }",
        "}",
        "",
        "fn finish_drained(&self, source: &gst::Object) {",
        "    let mut drained = Vec::new();",
        "    {",
        "        let (slots, _) = self.slots();",
        *[f"    {line}" for line in collect],
        "    }",
        "    for (slot, id) in drained {",
        "        self.finish(slot, &id);",
        "    }",
        "}",
    ]


def render_pipeline(program: ProgramPlan, graph: Graph, renderer: ScopeRenderer) -> list[str]:
    cls = f"{program.type_name}Pipeline"
    lines = ["", "// ---- Pipeline", *_config(program)]
    if program.slots:
        fields = [f"    {s.ident}: rt::Slot<{s.component.type_name}Params>," for s in program.slots]
        lines += ["", "struct Slots {", *fields, "}"]
    slots_field = "slots: Mutex<Slots>,\n    " if program.slots else ""
    state = STATE.replace("SLOTS_FIELD    ", slots_field).replace("PIPELINE", cls)
    lines += [
        state.replace("NAME", program.name).rstrip("\n"),
        "",
        f"impl {cls} {{",
        *_new(program, graph, renderer),
    ]
    methods: list[str] = []
    if program.slots:
        methods += [
            "",
            "fn slots(&self) -> (std::sync::MutexGuard<'_, Slots>, rt::Scope<'_>) {",
            "    let inner = &self.inner;",
            "    let (pipeline, elements, host) = (&inner.pipeline, &inner.elements, &inner.host);",
            "    let scope = rt::Scope { pipeline, elements, host };",
            "    (inner.slots.lock().unwrap(), scope)",
            "}",
        ]
        for slot in program.slots:
            methods += _slot_methods(slot)
    for function in program.functions:
        methods += function_method(function, program)
    methods += call_method(program) + dispatch_method(program) + _drain_methods(program)
    lines += [f"    {line}".rstrip() for line in methods] + ["}"]
    lines.append(LIFECYCLE.replace("PIPELINE", cls).rstrip("\n"))
    return [
        *lines,
        "",
        "// ---- Demo (replace with your application)",
        "",
        "fn main() -> Result<()> {",
        f"    let pipeline = {cls}::new(Config::default())?;",
        "    pipeline.connect_message(|message| {",
        '        println!("message {} from {:?}: {:?}", message.name, message.source, message.fields);',
        "    });",
        "    pipeline.run()",
        "}",
    ]
