"""Introspection of element factories into catalog models."""

from __future__ import annotations

from typing import Any

from pipelab.catalog.classify import classify_categories, classify_family, media_types
from pipelab.catalog.models import (
    ElementInfo,
    EnumValue,
    PadSummary,
    PadTemplateInfo,
    PropertyInfo,
    PropertyType,
)
from pipelab.catalog.previewable import preview_kind_for
from pipelab.gst import GObject, Gst
from pipelab.gst.values import to_json_value

# GstParamFlags (G_PARAM_USER_SHIFT = 8); defined here to avoid depending on
# how a particular PyGObject version exposes them.
PARAM_CONTROLLABLE = 1 << 9
PARAM_MUTABLE_READY = 1 << 10
PARAM_MUTABLE_PAUSED = 1 << 11
PARAM_MUTABLE_PLAYING = 1 << 12

_FUNDAMENTAL_TYPES: dict[str, PropertyType] = {
    "gboolean": "boolean",
    "gint": "int",
    "gchar": "int",
    "guint": "uint",
    "guchar": "uint",
    "glong": "int64",
    "gint64": "int64",
    "gulong": "uint64",
    "guint64": "uint64",
    "gfloat": "float",
    "gdouble": "double",
    "gchararray": "string",
    "GEnum": "enum",
    "GFlags": "flags",
}
_NAMED_TYPES: dict[str, PropertyType] = {
    "GstCaps": "caps",
    "GstFraction": "fraction",
    "GstStructure": "structure",
    "GstValueArray": "array",
    "GstValueList": "array",
    "GValueArray": "array",
    "GStrv": "array",
}
_HIDDEN_OWNERS = {"GObject", "GstObject", "GstPad", "GstProxyPad", "GstGhostPad"}
_NO_DEFAULT_TYPES = {"object", "boxed", "other"}
_PRESENCE = {
    Gst.PadPresence.ALWAYS: "always",
    Gst.PadPresence.SOMETIMES: "sometimes",
    Gst.PadPresence.REQUEST: "request",
}


def property_type(gtype: GObject.GType) -> PropertyType:
    name = gtype.name
    if name in _NAMED_TYPES:
        return _NAMED_TYPES[name]
    fundamental = GObject.type_name(gtype.fundamental)
    if fundamental in _FUNDAMENTAL_TYPES:
        return _FUNDAMENTAL_TYPES[fundamental]
    if gtype.is_a(Gst.Pad.__gtype__):
        return "pad"
    if fundamental == "GObject":
        return "object"
    if fundamental == "GBoxed":
        return "boxed"
    return "other"


def _mutability(flags: int, construct_only: bool) -> str:
    if construct_only:
        return "null"
    if flags & PARAM_MUTABLE_PLAYING:
        return "playing"
    if flags & PARAM_MUTABLE_PAUSED:
        return "paused"
    if flags & PARAM_MUTABLE_READY:
        return "ready"
    return "unknown"


def _enum_values(gtype: GObject.GType, kind: PropertyType) -> list[EnumValue]:
    if kind == "enum":
        values = _enumerate_enum(gtype)
    elif kind == "flags":
        values = _enumerate_flags(gtype)
    else:
        return []
    return [EnumValue(value=v, nick=nick, name=name) for v, nick, name in values]


def _enumerate_enum(gtype: GObject.GType) -> list[tuple[int, str, str]]:
    pytype = gtype.pytype
    if pytype is None or not hasattr(pytype, "__enum_values__"):
        return []
    return [(int(v), v.value_nick, v.value_name) for v in pytype.__enum_values__.values()]


def _enumerate_flags(gtype: GObject.GType) -> list[tuple[int, str, str]]:
    pytype = gtype.pytype
    if pytype is None or not hasattr(pytype, "__flags_values__"):
        return []
    values = []
    for value in pytype.__flags_values__.values():
        nicks, names = list(value.value_nicks or []), list(value.value_names or [])
        if len(nicks) == 1:
            values.append((int(value), nicks[0], names[0]))
    return sorted(set(values))


def _default_value(pspec: GObject.ParamSpec, kind: PropertyType, instance: Any) -> Any:
    if kind in _NO_DEFAULT_TYPES:
        return None
    readable = bool(pspec.flags & GObject.ParamFlags.READABLE)
    if instance is not None and readable:
        try:
            return to_json_value(instance.get_property(pspec.name))
        except Exception:  # noqa: BLE001 - some getters fail outside a pipeline
            pass
    try:
        return to_json_value(pspec.get_default_value())
    except Exception:  # noqa: BLE001
        return None


def _bounds(pspec: GObject.ParamSpec) -> tuple[Any, Any]:
    minimum = getattr(pspec, "minimum", None)
    maximum = getattr(pspec, "maximum", None)
    return to_json_value(minimum), to_json_value(maximum)


def describe_property(pspec: GObject.ParamSpec, instance: Any = None) -> PropertyInfo:
    flags = int(pspec.flags)
    kind = property_type(pspec.value_type)
    construct_only = bool(flags & GObject.ParamFlags.CONSTRUCT_ONLY)
    minimum, maximum = _bounds(pspec) if kind not in ("enum", "flags", "boolean") else (None, None)
    return PropertyInfo(
        name=pspec.name,
        nick=pspec.nick or "",
        blurb=pspec.blurb or "",
        type=kind,
        value_type=pspec.value_type.name,
        default=_default_value(pspec, kind, instance),
        minimum=minimum,
        maximum=maximum,
        enum_values=_enum_values(pspec.value_type, kind),
        readable=bool(flags & GObject.ParamFlags.READABLE),
        writable=bool(flags & GObject.ParamFlags.WRITABLE),
        construct_only=construct_only,
        mutable=_mutability(flags, construct_only),
        controllable=bool(flags & PARAM_CONTROLLABLE),
    )


def describe_properties(gtype: GObject.GType, instance: Any = None) -> list[PropertyInfo]:
    properties = []
    for pspec in GObject.list_properties(gtype):
        if pspec.owner_type.name in _HIDDEN_OWNERS:
            continue
        properties.append(describe_property(pspec, instance))
    return properties


def _pad_properties(element: Gst.Element | None, template_name: str) -> list[PropertyInfo]:
    if element is None:
        return []
    template = element.get_pad_template(template_name)
    gtype = template.props.gtype if template is not None else None
    if gtype is None or not gtype.is_a(Gst.Pad.__gtype__) or gtype.name == "GstPad":
        return []
    return describe_properties(gtype)


def describe_pad_template(static: Gst.StaticPadTemplate, element: Gst.Element | None) -> PadTemplateInfo:
    caps = static.get_caps().to_string()
    return PadTemplateInfo(
        name=static.name_template,
        direction="src" if static.direction == Gst.PadDirection.SRC else "sink",
        presence=_PRESENCE[static.presence],
        media_types=media_types(caps),
        caps=caps,
        properties=_pad_properties(element, static.name_template),
    )


def _hierarchy(gtype: GObject.GType) -> list[str]:
    names = []
    while gtype is not None and gtype.name not in ("GObject", "GInitiallyUnowned", "invalid"):
        names.append(gtype.name)
        gtype = gtype.parent
    return names


def _uri_info(factory: Gst.ElementFactory) -> tuple[list[str], str | None]:
    uri_type = factory.get_uri_type()
    if uri_type == Gst.URIType.SRC:
        return list(factory.get_uri_protocols() or []), "src"
    if uri_type == Gst.URIType.SINK:
        return list(factory.get_uri_protocols() or []), "sink"
    return [], None


def _plugin_fields(plugin: Gst.Plugin | None) -> dict[str, str]:
    if plugin is None:
        return {"package": "", "origin": "", "source": ""}
    return {
        "package": plugin.get_package() or "",
        "origin": plugin.get_origin() or "",
        "source": plugin.get_source() or "",
    }


def _to_summary(template: PadTemplateInfo) -> PadSummary:
    return PadSummary.model_validate(template.model_dump(include=set(PadSummary.model_fields)))


def describe_factory(factory: Gst.ElementFactory, instantiate: bool = True) -> ElementInfo:
    """Describe an element factory. ``instantiate`` reads real default values."""
    loaded = factory.load() or factory
    gtype = loaded.get_element_type()
    element = loaded.create(None) if instantiate else None
    plugin_fields = _plugin_fields(loaded.get_plugin())
    klass = loaded.get_metadata(Gst.ELEMENT_METADATA_KLASS) or ""
    name = loaded.get_name()
    templates = [describe_pad_template(t, element) for t in loaded.get_static_pad_templates()]
    properties = describe_properties(gtype, element)
    uri_protocols, uri_type = _uri_info(loaded)
    return ElementInfo(
        name=name,
        long_name=loaded.get_metadata(Gst.ELEMENT_METADATA_LONGNAME) or "",
        klass=klass,
        description=loaded.get_metadata(Gst.ELEMENT_METADATA_DESCRIPTION) or "",
        author=loaded.get_metadata(Gst.ELEMENT_METADATA_AUTHOR) or "",
        rank=loaded.get_rank(),
        plugin=loaded.get_plugin_name() or "",
        family=classify_family(plugin_fields["source"], plugin_fields["origin"]),
        categories=classify_categories(name, klass),
        preview=preview_kind_for(name),
        pads=[_to_summary(t) for t in templates],
        hierarchy=_hierarchy(gtype),
        interfaces=[i.name for i in GObject.type_interfaces(gtype)],
        uri_protocols=uri_protocols,
        uri_type=uri_type,
        pad_templates=templates,
        properties=properties,
        selectors=[p.name for p in properties if p.type == "pad" and p.writable],
        introspected=element is not None,
        **plugin_fields,
    )
