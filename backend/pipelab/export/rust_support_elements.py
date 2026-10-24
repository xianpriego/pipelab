"""Generic Rust support (continues ``mod rt``): elements, links, ghost pads, events."""

ELEMENTS = r"""
    pub type Elements = BTreeMap<String, gst::Element>;

    pub fn make_element(
        container: &gst::Bin,
        factory: &str,
        name: &str,
        properties: &[(&str, &str)],
    ) -> Result<gst::Element> {
        let mut builder = gst::ElementFactory::make(factory).name(name);
        for (key, value) in properties {
            builder = builder.property_from_str(key, value);
        }
        let element =
            builder.build().with_context(|| format!("element '{factory}' is not installed"))?;
        container.add(&element)?;
        Ok(element)
    }

    /// An existing pad, or a newly requested one; the flag tells if it was requested.
    pub fn pad_of(element: &gst::Element, name: &str) -> Result<(gst::Pad, bool)> {
        if let Some(pad) = element.static_pad(name) {
            return Ok((pad, false));
        }
        let pad = element
            .request_pad_simple(name)
            .ok_or_else(|| anyhow!("{} has no pad {name}", element.name()))?;
        Ok((pad, true))
    }

    pub fn get<'a>(elements: &'a Elements, name: &str) -> Result<&'a gst::Element> {
        elements.get(name).ok_or_else(|| anyhow!("no element {name}"))
    }

    /// `name`, or `instance/inner` for elements inside component instances.
    pub fn find_element(
        pipeline: &gst::Pipeline,
        elements: &Elements,
        path: &str,
    ) -> Result<gst::Element> {
        let mut parts = path.split('/');
        let first = parts.next().unwrap_or_default();
        let found = elements.get(first).cloned().or_else(|| pipeline.by_name(first));
        let mut element = found.ok_or_else(|| anyhow!("no element {path}"))?;
        for part in parts {
            let bin = element
                .downcast::<gst::Bin>()
                .map_err(|_| anyhow!("{path}: not a bin before {part}"))?;
            element = bin.by_name(part).ok_or_else(|| anyhow!("no element {path}"))?;
        }
        Ok(element)
    }

    pub fn configure_pad(
        element: &gst::Element,
        pad: &str,
        properties: &[(&str, &str)],
    ) -> Result<()> {
        let (pad, _) = pad_of(element, pad)?;
        for (key, value) in properties {
            pad.set_property_from_str(key, value);
        }
        Ok(())
    }

    pub fn link(
        elements: &Elements,
        src: &str,
        src_pad: &str,
        sink: &str,
        sink_pad: &str,
    ) -> Result<()> {
        let (source, _) = pad_of(get(elements, src)?, src_pad)?;
        let (target, _) = pad_of(get(elements, sink)?, sink_pad)?;
        source
            .link(&target)
            .with_context(|| format!("could not link {src}.{src_pad} to {sink}.{sink_pad}"))?;
        Ok(())
    }

    pub fn matches(pad: &gst::Pad, name: &str) -> bool {
        pad.name() == name || pad.pad_template().is_some_and(|t| t.name_template() == name)
    }

    /// Links a *sometimes* pad (name or template `src_pad`) once it appears.
    pub fn link_dynamic(
        elements: &Elements,
        src: &str,
        src_pad: &str,
        sink: &str,
        sink_pad: &str,
    ) -> Result<()> {
        let (target, _) = pad_of(get(elements, sink)?, sink_pad)?;
        let wanted = src_pad.to_string();
        get(elements, src)?.connect_pad_added(move |element, pad| {
            if !matches(pad, &wanted)
                || target.is_linked()
                || !pad.query_caps(None).can_intersect(&target.query_caps(None))
            {
                return;
            }
            if let Err(err) = pad.link(&target) {
                eprintln!("could not link {}.{}: {err:?}", element.name(), pad.name());
            }
        });
        Ok(())
    }

    /// Sets a property like gst-launch; GstPad-typed properties take a pad name.
    pub fn apply_value(
        element: &gst::Element,
        property: &str,
        value: &Value,
        pad: Option<&str>,
    ) -> Result<()> {
        let Some(text) = value.text() else { return Ok(()) };
        let target: gst::Object = match pad {
            Some(name) if !name.is_empty() => pad_of(element, name)?.0.upcast(),
            _ => element.clone().upcast(),
        };
        let pspec = target
            .find_property(property)
            .ok_or_else(|| anyhow!("{} has no property {property}", target.name()))?;
        if pspec.value_type().is_a(gst::Pad::static_type()) {
            let pad = element
                .static_pad(&text)
                .ok_or_else(|| anyhow!("{} has no pad {text}", element.name()))?;
            target.set_property(property, &pad);
        } else {
            target.set_property_from_str(property, &text);
        }
        Ok(())
    }

    fn ghost(container: &gst::Bin, inner: &gst::Pad, port: &str) -> Result<()> {
        let proxy = gst::GhostPad::builder_with_target(inner)?.name(port).build();
        if container.current_state() != gst::State::Null {
            proxy.set_active(true)?;
        }
        container.add_pad(&proxy)?;
        Ok(())
    }

    /// Ghost pad named `port` on `container` for an inner pad (added later for sometimes pads).
    pub fn expose_port(
        container: &gst::Bin,
        element: &gst::Element,
        pad: &str,
        port: &str,
        presence: &str,
    ) -> Result<()> {
        if presence != "sometimes" {
            return ghost(container, &pad_of(element, pad)?.0, port);
        }
        let bin = container.downgrade();
        let (wanted, port) = (pad.to_string(), port.to_string());
        element.connect_pad_added(move |_, inner| {
            let Some(bin) = bin.upgrade() else { return };
            if matches(inner, &wanted) && bin.static_pad(&port).is_none() {
                if let Err(err) = ghost(&bin, inner, &port) {
                    eprintln!("could not expose {port}: {err:#}");
                }
            }
        });
        Ok(())
    }

    pub fn structure(name: &str, fields: &[(&str, Value)]) -> gst::Structure {
        let mut builder = gst::Structure::builder(name);
        for (key, value) in fields {
            builder = match value {
                Value::Null => builder,
                Value::Bool(b) => builder.field(*key, *b),
                Value::Int(i) => builder.field(*key, *i),
                Value::Float(f) => builder.field(*key, *f),
                Value::Str(s) => builder.field(*key, s.as_str()),
            };
        }
        builder.build()
    }

    pub fn make_events(
        kind: &str,
        downstream: bool,
        name: Option<&str>,
        fields: &[(&str, Value)],
    ) -> Vec<gst::Event> {
        match (kind, downstream) {
            ("eos", _) => vec![gst::event::Eos::new()],
            ("flush", _) => vec![gst::event::FlushStart::new(), gst::event::FlushStop::new(true)],
            ("force-key-unit", true) => {
                vec![gst_video::DownstreamForceKeyUnitEvent::builder().all_headers(true).build()]
            }
            ("force-key-unit", false) => {
                vec![gst_video::UpstreamForceKeyUnitEvent::builder().all_headers(true).build()]
            }
            (_, true) => vec![gst::event::CustomDownstream::new(structure(
                name.unwrap_or("pipelab-event"),
                fields,
            ))],
            (_, false) => vec![gst::event::CustomUpstream::new(structure(
                name.unwrap_or("pipelab-event"),
                fields,
            ))],
        }
    }

    /// Sends events through a pad of `element` (by name), or to the element itself.
    pub fn send_to(
        element: &gst::Element,
        pad: &Value,
        events: Vec<gst::Event>,
        downstream: bool,
    ) -> Result<()> {
        match pad.text() {
            Some(name) if !name.is_empty() => {
                send_events(&pad_of(element, &name)?.0, events, downstream)
            }
            _ => {
                for event in events {
                    element.send_event(event);
                }
            }
        }
        Ok(())
    }

    /// Downstream events are pushed from src pads and sent into sink pads (and vice versa).
    pub fn send_events(pad: &gst::Pad, events: Vec<gst::Event>, downstream: bool) {
        let is_src = pad.direction() == gst::PadDirection::Src;
        for event in events {
            let _ =
                if downstream == is_src { pad.push_event(event) } else { pad.send_event(event) };
        }
    }
"""
