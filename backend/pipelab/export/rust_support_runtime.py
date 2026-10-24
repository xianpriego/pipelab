"""Generic Rust support (continues ``mod rt``): a rule set wired to the pads it watches."""

RULE_SET = r"""
    /// A rule set attached to the pads of an element.
    pub struct RuleSet<R: Rules> {
        me: Weak<RuleSet<R>>,
        core: Core,
        rules: Mutex<R>,
    }

    impl<R: Rules> RuleSet<R> {
        /// Watches `pad` (name or template) of `element`, or all its sink pads when `None`.
        #[allow(clippy::too_many_arguments)]
        pub fn attach(
            host: &ProbeHost,
            elements: &Elements,
            element: &str,
            pad: Option<&str>,
            probe_id: String,
            instance: &str,
            node: &str,
            rules: R,
        ) -> Result<()> {
            let target = get(elements, element)?.clone();
            let set = Arc::new_cyclic(|me| RuleSet {
                me: me.clone(),
                core: Core {
                    element: target.clone(),
                    elements: elements.clone(),
                    probe_id,
                    instance: instance.to_string(),
                    node: node.to_string(),
                    pad_spec: pad.map(str::to_string),
                    host: host.downgrade(),
                    enabled: AtomicBool::new(true),
                    pads: Mutex::default(),
                    blocks: Mutex::default(),
                    track: Mutex::default(),
                },
                rules: Mutex::new(rules),
            });
            for existing in target.pads() {
                set.watch(&existing);
            }
            let weak = Arc::downgrade(&set);
            target.connect_pad_added(move |_, pad| {
                if let Some(set) = weak.upgrade() {
                    set.watch(pad);
                }
            });
            host.register(set);
            Ok(())
        }

        fn watch(&self, pad: &gst::Pad) {
            let wanted = match &self.core.pad_spec {
                Some(spec) => matches(pad, spec),
                None => pad.direction() == gst::PadDirection::Sink,
            };
            let mut pads = self.core.pads.lock().unwrap();
            if !wanted || pads.contains(pad) {
                return;
            }
            pads.push(pad.clone());
            let me = self.me.clone();
            let kinds = gst::PadProbeType::BUFFER
                | gst::PadProbeType::BUFFER_LIST
                | gst::PadProbeType::EVENT_DOWNSTREAM;
            pad.add_probe(kinds, move |pad, info| match me.upgrade() {
                Some(set) => set.on_probe(pad, info),
                None => gst::PadProbeReturn::Remove,
            });
        }

        fn on_probe(&self, pad: &gst::Pad, info: &mut gst::PadProbeInfo) -> gst::PadProbeReturn {
            if !self.core.enabled() || !self.core.started() {
                return gst::PadProbeReturn::Ok;
            }
            let verdict = match &info.data {
                Some(gst::PadProbeData::Buffer(buffer)) => self.buffer(pad, buffer),
                Some(gst::PadProbeData::BufferList(list)) => {
                    let verdicts: Vec<Verdict> =
                        list.iter().map(|buffer| self.buffer(pad, buffer)).collect();
                    if verdicts.contains(&Verdict::Drop) {
                        Verdict::Drop
                    } else {
                        Verdict::Pass
                    }
                }
                Some(gst::PadProbeData::Event(event)) => {
                    let name = event.type_().name();
                    let ctx = Ctx { pad: Some(pad), ..Ctx::new(Value::from(name.as_str())) };
                    self.rules.lock().unwrap().on_event(&self.core, &ctx, name.as_str())
                }
                _ => Verdict::Pass,
            };
            if verdict == Verdict::Drop {
                gst::PadProbeReturn::Drop
            } else {
                gst::PadProbeReturn::Ok
            }
        }

        fn buffer(&self, pad: &gst::Pad, buffer: &gst::BufferRef) -> Verdict {
            let resumed = self.core.track_buffer(buffer);
            let ctx = Ctx { pad: Some(pad), buffer: Some(buffer), ..Ctx::new(Value::Null) };
            let mut rules = self.rules.lock().unwrap();
            if resumed {
                rules.on_resumed(&self.core, &ctx);
            }
            rules.on_buffer(&self.core, &ctx)
        }

        fn check_idle(&self, index: usize, ms: u64) {
            let idle = self.core.idle_ms();
            if idle >= ms && self.core.fire_idle(index) {
                let ctx = Ctx { idle_ms: Some(idle), ..Ctx::new(Value::Null) };
                self.rules.lock().unwrap().on_idle(&self.core, &ctx, index);
            }
        }
    }

    impl<R: Rules> RuleSetHandle for RuleSet<R> {
        fn probe_id(&self) -> &str {
            &self.core.probe_id
        }

        fn start(&self) {
            self.core.mark_started(R::IDLE.len());
            for (index, ms) in R::IDLE.iter().copied().enumerate() {
                let me = self.me.clone();
                glib::timeout_add(Duration::from_millis((ms / 4).clamp(10, 100)), move || match me
                    .upgrade()
                {
                    Some(set) if set.core.enabled() => {
                        set.check_idle(index, ms);
                        glib::ControlFlow::Continue
                    }
                    _ => glib::ControlFlow::Break,
                });
            }
            for (index, ms) in R::INTERVALS.iter().copied().enumerate() {
                let me = self.me.clone();
                glib::timeout_add(Duration::from_millis(ms.max(1)), move || match me.upgrade() {
                    Some(set) if set.core.enabled() => {
                        set.rules.lock().unwrap().on_interval(
                            &set.core,
                            &Ctx::new(Value::Null),
                            index,
                        );
                        glib::ControlFlow::Continue
                    }
                    _ => glib::ControlFlow::Break,
                });
            }
            self.rules.lock().unwrap().on_start(&self.core, &Ctx::new(Value::Null));
        }

        fn signal(&self, name: &str, value: Value) {
            if self.core.enabled() {
                self.rules.lock().unwrap().on_signal(&self.core, &Ctx::new(value), name);
            }
        }

        fn offer_property(&self, element: &str, property: &str, value: &Value) -> bool {
            let core = &self.core;
            let path = if core.instance.is_empty() {
                core.node.clone()
            } else {
                format!("{}/{}", core.instance, core.node)
            };
            core.enabled()
                && path == element
                && self.rules.lock().unwrap().on_property(core, &Ctx::new(value.clone()), property)
        }

        fn remove(&self) {
            self.core.remove();
        }
    }
"""
