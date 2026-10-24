"""Generic Rust support (continues ``mod rt``): what rules can read and do (``impl Core``)."""

CORE_IMPL = r"""
    impl Core {
        pub fn enabled(&self) -> bool {
            self.enabled.load(Ordering::SeqCst)
        }
        fn started(&self) -> bool {
            self.track.lock().unwrap().started.is_some()
        }
        fn mark_started(&self, idle_rules: usize) {
            let mut track = self.track.lock().unwrap();
            let now = Instant::now();
            track.started = Some(now);
            track.last_buffer = Some(now);
            track.idle_fired = vec![false; idle_rules];
        }
        /// Updates timing state; true when the buffer ends an idle period.
        fn track_buffer(&self, buffer: &gst::BufferRef) -> bool {
            let mut track = self.track.lock().unwrap();
            let now = Instant::now();
            track.arrivals.retain(|t| now.duration_since(*t) < Duration::from_secs(1));
            track.arrivals.push_back(now);
            let pts = buffer.pts().map(|t| t.nseconds());
            track.gap_ms = match (pts, track.last_pts) {
                (Some(pts), Some(last)) => Some((pts as f64 - last as f64) / 1e6),
                _ => None,
            };
            track.backwards = track.gap_ms.is_some_and(|gap| gap < 0.0);
            track.last_pts = pts.or(track.last_pts);
            track.last_buffer = Some(now);
            let resumed = track.idle_fired.iter().any(|fired| *fired);
            track.idle_fired.iter_mut().for_each(|fired| *fired = false);
            resumed
        }
        fn idle_ms(&self) -> u64 {
            let track = self.track.lock().unwrap();
            track.last_buffer.map_or(0, |t| t.elapsed().as_millis() as u64)
        }
        fn fire_idle(&self, index: usize) -> bool {
            let mut track = self.track.lock().unwrap();
            match track.idle_fired.get_mut(index) {
                Some(fired) if !*fired => {
                    *fired = true;
                    true
                }
                _ => false,
            }
        }

        pub fn builtin(&self, name: &str, ctx: &Ctx) -> Value {
            match name {
                "value" => ctx.value.clone(),
                "pad" => ctx.pad.map_or(Value::Null, |p| Value::from(p.name().as_str())),
                "pts" => {
                    Value::from(ctx.buffer.and_then(|b| b.pts()).map(|t| t.nseconds() as f64 / 1e9))
                }
                "size" => Value::from(ctx.buffer.map(|b| b.size() as i64)),
                "time" => {
                    let started = self.track.lock().unwrap().started;
                    Value::Float(started.map_or(0.0, |t| t.elapsed().as_secs_f64()))
                }
                "instance" => Value::from(self.instance.as_str()),
                "node" => Value::from(self.node.as_str()),
                "idle_ms" => Value::from(ctx.idle_ms.map(|v| v as i64)),
                _ => Value::Null,
            }
        }
        pub fn is_keyframe(&self, ctx: &Ctx) -> bool {
            ctx.buffer.is_some_and(|b| !b.flags().contains(gst::BufferFlags::DELTA_UNIT))
        }
        /// `flag` is a GstBufferFlags nick (delta-unit, discont, gap, header…).
        pub fn has_flag(&self, ctx: &Ctx, flag: &str) -> bool {
            let class = glib::FlagsClass::with_type(gst::BufferFlags::static_type());
            let bits = class.and_then(|c| c.value_by_nick(flag).map(|v| v.value())).unwrap_or(0);
            let wanted = gst::BufferFlags::from_bits_truncate(bits);
            !wanted.is_empty() && ctx.buffer.is_some_and(|b| b.flags().contains(wanted))
        }
        pub fn every(&self, key: &str, n: u64) -> bool {
            let mut track = self.track.lock().unwrap();
            let counter = track.counters.entry(key.to_string()).or_insert(0);
            *counter += 1;
            *counter % n.max(1) == 0
        }
        pub fn rate(&self) -> Value {
            Value::Float(self.track.lock().unwrap().arrivals.len() as f64)
        }
        pub fn gap_ms(&self) -> Option<f64> {
            self.track.lock().unwrap().gap_ms
        }
        pub fn backwards(&self) -> bool {
            self.track.lock().unwrap().backwards
        }
        pub fn caps_field(&self, ctx: &Ctx, field: &str) -> Value {
            let pad = ctx.pad.cloned().or_else(|| self.pads.lock().unwrap().first().cloned());
            let Some(caps) = pad.and_then(|p| p.current_caps()) else { return Value::Null };
            let Some(structure) = caps.structure(0) else { return Value::Null };
            if let Ok(v) = structure.get::<i32>(field) {
                Value::Int(v.into())
            } else if let Ok(v) = structure.get::<bool>(field) {
                Value::Bool(v)
            } else if let Ok(v) = structure.get::<&str>(field) {
                Value::from(v)
            } else {
                structure
                    .value(field)
                    .ok()
                    .and_then(|v| v.serialize().ok())
                    .map_or(Value::Null, |s| Value::from(s.as_str()))
            }
        }
        pub fn chance(&self, percent: f64) -> bool {
            let mut track = self.track.lock().unwrap();
            if track.seed == 0 {
                track.seed = Instant::now().elapsed().as_nanos() as u64 | 0x9E37_79B9_7F4A_7C15;
            }
            track.seed ^= track.seed << 13;
            track.seed ^= track.seed >> 7;
            track.seed ^= track.seed << 17;
            (track.seed % 10_000) as f64 / 100.0 < percent
        }

        fn pad_for(&self, ctx: &Ctx, pad: &Value) -> Option<gst::Pad> {
            match pad.text() {
                Some(name) if !name.is_empty() => {
                    pad_of(&self.element, &name).ok().map(|(pad, _)| pad)
                }
                _ => ctx.pad.cloned().or_else(|| self.pads.lock().unwrap().first().cloned()),
            }
        }
        pub fn post(&self, name: &str, fields: Vec<(&str, Value)>) {
            let message = gst::message::Application::builder(structure(name, &fields))
                .src(&self.element)
                .build();
            let _ = self.element.post_message(message);
        }
        pub fn set_property(&self, node: &str, property: &str, value: &Value, pad: &Value) {
            let result = get(&self.elements, node)
                .and_then(|e| apply_value(e, property, value, pad.text().as_deref()));
            if let Err(err) = result {
                eprintln!("[{}] set-property failed: {err:#}", self.probe_id);
            }
        }
        pub fn send(
            &self,
            kind: &str,
            downstream: bool,
            ctx: &Ctx,
            pad: &Value,
            name: Option<&str>,
            fields: Vec<(&str, Value)>,
        ) {
            if let Some(target) = self.pad_for(ctx, pad) {
                send_events(&target, make_events(kind, downstream, name, &fields), downstream);
            }
        }
        pub fn request_keyframe(&self, ctx: &Ctx, pad: &Value) {
            self.send("force-key-unit", false, ctx, pad, None, Vec::new());
        }
        pub fn block(&self) {
            let mut blocks = self.blocks.lock().unwrap();
            for pad in self.pads.lock().unwrap().iter() {
                if blocks.iter().all(|(blocked, _)| blocked != pad) {
                    if let Some(id) = pad.add_probe(gst::PadProbeType::BLOCK_DOWNSTREAM, |_, _| {
                        gst::PadProbeReturn::Ok
                    }) {
                        blocks.push((pad.clone(), id));
                    }
                }
            }
        }
        pub fn unblock(&self) {
            for (pad, id) in self.blocks.lock().unwrap().drain(..) {
                pad.remove_probe(id);
            }
        }
        pub fn remove(&self) {
            self.enabled.store(false, Ordering::SeqCst);
            self.unblock();
        }
        pub fn log(&self, rule_set: &str, message: &str, level: &str, ctx: &Ctx, vars: &Vars) {
            let mut text = message.to_string();
            for name in ["value", "pad", "pts", "size", "time", "instance", "node", "idle_ms"] {
                text = text.replace(&format!("{{{name}}}"), &self.builtin(name, ctx).as_string());
            }
            for (name, value) in vars.0.iter() {
                text = text.replace(&format!("{{{name}}}"), &value.as_string());
            }
            eprintln!("[{rule_set}] {level}: {text}");
        }
        pub fn defer(&self, job: Deferred) {
            if let Some(inner) = self.host.upgrade() {
                ProbeHost { inner }.defer(job);
            }
        }
        /// Id of another rule set of the same scope (instance).
        pub fn sibling(&self, probe: &str) -> String {
            if self.instance.is_empty() {
                probe.to_string()
            } else {
                format!("{}/{probe}", self.instance)
            }
        }
    }
"""
