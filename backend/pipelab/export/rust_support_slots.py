"""Generic Rust support (closes ``mod rt``): slots of component instances."""

SLOTS = r"""
    /// Values of a component's parameters (implemented by each `*Params` type).
    pub trait Params: Clone + Send + 'static {
        fn value(&self, name: &str) -> Value;
        fn from_values(values: &[(String, Value)]) -> Self;
    }

    pub type Builder<P> = fn(&str, &P, &ProbeHost) -> Result<gst::Bin>;

    /// Connects a port of every instance to a pad of the static graph.
    pub struct SlotLink {
        pub port: &'static str,
        pub src: bool,
        pub element: &'static str,
        pub pad: &'static str,
        pub properties: Vec<(&'static str, Value)>,
    }

    struct Peer {
        port: &'static str,
        src: bool,
        element: gst::Element,
        pad: gst::Pad,
        requested: bool,
    }

    struct Instance<P> {
        id: String,
        params: P,
        bin: gst::Bin,
        peers: Vec<Peer>,
        restart: bool,
    }

    /// What slots need from the pipeline.
    pub struct Scope<'a> {
        pub pipeline: &'a gst::Pipeline,
        pub elements: &'a Elements,
        pub host: &'a ProbeHost,
    }

    fn link_pads(
        ghost: &gst::Pad,
        peer: &gst::Pad,
        src: bool,
    ) -> Result<gst::PadLinkSuccess, gst::PadLinkError> {
        if src {
            ghost.link(peer)
        } else {
            peer.link(ghost)
        }
    }

    fn connect(bin: &gst::Bin, port: &str, src: bool, peer: &gst::Pad) -> Result<()> {
        if let Some(ghost) = bin.static_pad(port) {
            link_pads(&ghost, peer, src)
                .with_context(|| format!("could not link {}.{port}", bin.name()))?;
            return Ok(());
        }
        let (port, peer) = (port.to_string(), peer.clone());
        bin.connect_pad_added(move |bin, ghost| {
            if ghost.name() == port.as_str() {
                if let Err(err) = link_pads(ghost, &peer, src) {
                    eprintln!("could not link {}.{port}: {err:?}", bin.name());
                }
            }
        });
        Ok(())
    }

    /// N instances of a component linked to the static graph, added and removed while running.
    pub struct Slot<P: Params> {
        item: &'static str,
        builder: Builder<P>,
        links: Vec<SlotLink>,
        max: Option<usize>,
        instances: Vec<Instance<P>>,
        draining: Vec<Instance<P>>,
    }

    impl<P: Params> Slot<P> {
        pub fn new(
            item: &'static str,
            builder: Builder<P>,
            links: Vec<SlotLink>,
            max: Option<usize>,
        ) -> Self {
            Slot { item, builder, links, max, instances: Vec::new(), draining: Vec::new() }
        }

        fn next_id(&self) -> String {
            let taken =
                |id: &str| self.instances.iter().chain(self.draining.iter()).any(|i| i.id == id);
            (0..)
                .map(|index| format!("{}{index}", self.item))
                .find(|id| !taken(id))
                .unwrap_or_default()
        }

        fn resolve(value: &Value, id: &str, index: i64, params: &P) -> Value {
            if let Value::Str(text) = value {
                if let Some(rest) = text.strip_prefix("$$") {
                    return Value::from(format!("${rest}"));
                }
                if let Some(name) = text.strip_prefix('$') {
                    return match name {
                        "index" => Value::Int(index),
                        "id" => Value::from(id),
                        other => params.value(other),
                    };
                }
            }
            value.clone()
        }

        pub fn add(&mut self, scope: &Scope, params: P, id: Option<String>) -> Result<String> {
            if self.max.is_some_and(|max| self.instances.len() >= max) {
                bail!("at most {} {} instances", self.max.unwrap_or_default(), self.item);
            }
            let id = id.unwrap_or_else(|| self.next_id());
            if self.instances.iter().any(|i| i.id == id) {
                bail!("{} '{id}' already exists", self.item);
            }
            let fallback = self.instances.len() as i64;
            let index = id.strip_prefix(self.item).and_then(|n| n.parse().ok()).unwrap_or(fallback);
            let bin = (self.builder)(&id, &params, scope.host)?;
            scope.pipeline.add(&bin)?;
            let mut peers = Vec::new();
            for link in &self.links {
                let element = get(scope.elements, link.element)?.clone();
                let (pad, requested) = pad_of(&element, link.pad)?;
                for (name, value) in &link.properties {
                    let value = Self::resolve(value, &id, index, &params);
                    apply_value(&element, name, &value, Some(pad.name().as_str()))?;
                }
                connect(&bin, link.port, link.src, &pad)?;
                peers.push(Peer { port: link.port, src: link.src, element, pad, requested });
            }
            if scope.pipeline.current_state() != gst::State::Null {
                bin.sync_state_with_parent()?;
            }
            self.instances.push(Instance { id: id.clone(), params, bin, peers, restart: false });
            Ok(id)
        }

        pub fn list(&self) -> Vec<(String, P)> {
            self.instances.iter().map(|i| (i.id.clone(), i.params.clone())).collect()
        }

        /// Removes an instance; true when it drains first (completed later by `finish`).
        pub fn remove(&mut self, scope: &Scope, id: &str, restart: bool) -> Result<bool> {
            let position = self
                .instances
                .iter()
                .position(|i| i.id == id)
                .ok_or_else(|| anyhow!("no {} '{id}'", self.item))?;
            let mut instance = self.instances.remove(position);
            instance.restart = restart;
            let upstream: Vec<&Peer> = instance.peers.iter().filter(|p| !p.src).collect();
            if upstream.is_empty() {
                self.finalize(scope, instance)?;
                return Ok(false);
            }
            for peer in upstream {
                let ghost = instance.bin.static_pad(peer.port);
                peer.pad.add_probe(gst::PadProbeType::IDLE, move |pad, _| {
                    if let Some(ghost) = &ghost {
                        let _ = pad.unlink(ghost);
                        let _ = ghost.send_event(gst::event::Eos::new());
                    }
                    gst::PadProbeReturn::Remove
                });
            }
            self.draining.push(instance);
            Ok(true)
        }

        /// Ids of draining instances that an EOS forwarded by the pipeline comes from.
        pub fn drained(&self, source: &gst::Object) -> Vec<String> {
            self.draining
                .iter()
                .filter(|i| {
                    source == i.bin.upcast_ref::<gst::Object>() || source.has_as_ancestor(&i.bin)
                })
                .map(|i| i.id.clone())
                .collect()
        }

        /// Completes a drained removal (no-op when already done); re-adds it for a restart.
        pub fn finish(&mut self, scope: &Scope, id: &str) -> Result<()> {
            let Some(position) = self.draining.iter().position(|i| i.id == id) else {
                return Ok(());
            };
            let instance = self.draining.remove(position);
            self.finalize(scope, instance)
        }

        fn finalize(&mut self, scope: &Scope, instance: Instance<P>) -> Result<()> {
            instance.bin.set_state(gst::State::Null)?;
            for peer in &instance.peers {
                if let Some(ghost) = instance.bin.static_pad(peer.port) {
                    let _ =
                        if peer.src { ghost.unlink(&peer.pad) } else { peer.pad.unlink(&ghost) };
                }
                if peer.requested {
                    peer.element.release_request_pad(&peer.pad);
                }
            }
            scope.pipeline.remove(&instance.bin)?;
            scope.host.unregister_prefix(&format!("{}/", instance.id));
            if instance.restart {
                self.add(scope, instance.params, Some(instance.id))?;
            }
            Ok(())
        }
    }
}
"""
