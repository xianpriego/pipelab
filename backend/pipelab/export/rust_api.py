"""API functions of the Rust pipeline type: typed methods, `call` by name, deferred work."""

from __future__ import annotations

from pipelab.export.plan import FunctionPlan, ProgramPlan
from pipelab.export.rust_probes import RustValues
from pipelab.export.rust_syntax import rust_str, typed_literal, uses_name
from pipelab.graph.probes import Action

_ARG_TYPES = {"string": "&str", "int": "i64", "float": "f64", "bool": "bool"}
_FROM_VALUE = {"string": "v.as_string()", "int": "v.as_i64()", "float": "v.as_f64()", "bool": "v.as_bool()"}


class _FunctionActions:
    def __init__(self, program: ProgramPlan, value: RustValues, params: list[str]) -> None:
        self.slots = {s.slot.id: s for s in program.slots} | {s.slot.name: s for s in program.slots}
        self.functions = {f.function.name: f.ident for f in program.functions}
        self.value, self.params = value, params

    def statement(self, action: Action) -> str:
        v, kind = self.value, action.type
        node = f"&self.element({rust_str(action.node or '')})?"
        if kind == "set-property":
            prop = rust_str(action.property or "")
            if action.pad is not None:
                pad = f"{v(action.pad)}.text().as_deref()"
                return f"rt::apply_value({node}, {prop}, &{v(action.value)}, {pad})?;"
            return f"self.set_element_property({rust_str(action.node or '')}, {prop}, &{v(action.value)})?;"
        if kind == "post-message":
            return f"self.post({rust_str(action.name or 'message')}, {v.fields(action.fields)});"
        if kind in ("send-event", "request-keyframe"):
            event = action.event or "eos" if kind == "send-event" else "force-key-unit"
            down = "true" if kind == "send-event" and action.direction == "downstream" else "false"
            name = f"Some({rust_str(action.name)})" if action.name else "None"
            events = f"rt::make_events({rust_str(event)}, {down}, {name}, &{v.fields(action.fields)})"
            return f"rt::send_to({node}, &{v(action.pad)}, {events}, {down})?;"
        if kind == "log":
            values = ", ".join(f"({rust_str(p)}, Value::from({p}))" for p in self.params)
            text = rust_str(f"{action.level}: {action.message or ''}")
            return f'eprintln!("{{}}", rt::expand({text}, &[{values}]));'
        if kind == "signal":
            probe, name = rust_str(action.probe or ""), rust_str(action.name or "")
            return f"self.signal({probe}, {name}, {v(action.value)})?;"
        if kind == "call":
            function = self.functions.get(action.function or "", action.function or "")
            return f"self.call({rust_str(function)}, &{v.args(action.args)})?;"
        slot = self.slots.get(action.slot or "")
        if slot is None or kind not in ("add-instance", "remove-instance", "restart-instance"):
            return f"// {kind}: not applicable in a function"
        if kind == "add-instance":
            params = f"{slot.component.type_name}Params::from_values(&{v.args(action.params)})"
            return f"self.add_{slot.item}({params})?;"
        operation = "remove" if kind == "remove-instance" else "restart"
        return f"self.{operation}_{slot.item}(&{v(action.instance)}.as_string())?;"


def function_method(function: FunctionPlan, program: ProgramPlan) -> list[str]:
    params = function.function.params
    names = [p.name for p in params]
    actions = _FunctionActions(program, RustValues(set(), set(names), scope="function"), names)
    body = [actions.statement(a) for a in function.function.actions] + ["Ok(())"]
    arguments = "".join(
        f", {p.name if uses_name(p.name, body) else '_' + p.name}: {_ARG_TYPES[p.type]}" for p in params
    )
    defaults = ", ".join(f"`{p.name}` = {p.default!r}" for p in params if p.default is not None)
    lines = ["", f"/// {function.function.description or function.function.name}"]
    if defaults:
        lines.append(f"/// Defaults (used by `call`): {defaults}.")
    return [
        *lines,
        f"pub fn {function.ident}(&self{arguments}) -> Result<()> {{",
        *[f"    {b}" for b in body],
        "}",
    ]


def _typed_arg(kind: str, name: str, default: object) -> str:
    value = f"rt::arg(args, {rust_str(name)})"
    literal = typed_literal(kind, default) if default is not None else None  # type: ignore[arg-type]
    if kind == "string":
        fallback = f"|| {literal}" if literal else "String::new"
        return f"&{value}.map_or_else({fallback}, |v| v.as_string())"
    return f"{value}.and_then(|v| {_FROM_VALUE[kind]}).unwrap_or({literal or 'Default::default()'})"


def call_method(program: ProgramPlan) -> list[str]:
    lines = ["", "/// Calls an API function by name; missing arguments take their defaults."]
    if not program.functions:
        return [
            *lines,
            "pub fn call(&self, function: &str, _args: &[(String, Value)]) -> Result<()> {",
            '    bail!("no function {function}")',
            "}",
        ]
    arms = []
    for function in program.functions:
        args = ", ".join(_typed_arg(p.type, p.name, p.default) for p in function.function.params)
        arms.append(f"        {rust_str(function.function.name)} => self.{function.ident}({args}),")
    return [
        *lines,
        "pub fn call(&self, function: &str, args: &[(String, Value)]) -> Result<()> {",
        "    match function {",
        *arms,
        '        _ => bail!("no function {function}"),',
        "    }",
        "}",
    ]


def dispatch_method(program: ProgramPlan) -> list[str]:
    def arms(operation: str) -> list[str]:
        result = []
        for slot in program.slots:
            key = rust_str(slot.slot.id)
            if operation == "Add":
                call = (
                    f"self.add_{slot.item}({slot.component.type_name}Params::from_values(&params)).map(drop)"
                )
            elif operation == "Remove":
                call = f"self.remove_{slot.item}(&id.as_string())"
            else:
                call = f"self.restart_{slot.item}(&id.as_string()).map(drop)"
            result.append(f"            {key} => {call},")
        return result

    lines = [
        "",
        "/// Work that probe rules defer to the main loop.",
        "fn dispatch(&self, job: rt::Deferred) -> Result<()> {",
        "    match job {",
        "        rt::Deferred::Call(function, args) => self.call(&function, &args),",
    ]
    for operation, value in (("Add", "params"), ("Remove", "id"), ("Restart", "id")):
        if program.slots:
            lines += [
                f"        rt::Deferred::{operation}(slot, {value}) => match slot.as_str() {{",
                *arms(operation),
                '            _ => bail!("no slot {slot}"),',
                "        },",
            ]
        else:
            lines.append(f'        rt::Deferred::{operation}(slot, _) => bail!("no slot {{slot}}"),')
    return [*lines, "        rt::Deferred::Signal(..) => Ok(()), // handled by the probe host", "    }", "}"]
