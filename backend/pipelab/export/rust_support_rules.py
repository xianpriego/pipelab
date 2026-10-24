"""Generic Rust support for probe rule sets (continues ``mod rt``)."""

RULES = r"""
    /// Deferred work: never done inside a streaming thread.
    pub enum Deferred {
        Call(String, Vec<(String, Value)>),
        Add(String, Vec<(String, Value)>),
        Remove(String, Value),
        Restart(String, Value),
        Signal(String, String, Value),
    }

    pub trait RuleSetHandle: Send + Sync {
        fn probe_id(&self) -> &str;
        fn start(&self);
        fn signal(&self, name: &str, value: Value);
        fn offer_property(&self, element: &str, property: &str, value: &Value) -> bool;
        fn remove(&self);
    }

    type Dispatcher = Box<dyn Fn(Deferred) + Send + Sync>;

    #[derive(Default)]
    pub struct HostInner {
        rule_sets: Mutex<Vec<Arc<dyn RuleSetHandle>>>,
        started: AtomicBool,
        dispatcher: Mutex<Option<Dispatcher>>,
    }

    /// Rule sets of one pipeline: started together, reachable by id, deferring work to the main loop.
    #[derive(Clone, Default)]
    pub struct ProbeHost {
        inner: Arc<HostInner>,
    }

    impl ProbeHost {
        pub fn downgrade(&self) -> Weak<HostInner> {
            Arc::downgrade(&self.inner)
        }
        pub fn register(&self, rule_set: Arc<dyn RuleSetHandle>) {
            if self.started() {
                rule_set.start();
            }
            self.inner.rule_sets.lock().unwrap().push(rule_set);
        }
        pub fn started(&self) -> bool {
            self.inner.started.load(Ordering::SeqCst)
        }
        pub fn start(&self) {
            if !self.inner.started.swap(true, Ordering::SeqCst) {
                for rule_set in self.rule_sets() {
                    rule_set.start();
                }
            }
        }
        pub fn rule_sets(&self) -> Vec<Arc<dyn RuleSetHandle>> {
            self.inner.rule_sets.lock().unwrap().clone()
        }
        pub fn find(&self, probe_id: &str) -> Option<Arc<dyn RuleSetHandle>> {
            self.rule_sets().into_iter().find(|r| r.probe_id() == probe_id)
        }
        /// Disables and forgets the rule sets of a removed instance.
        pub fn unregister_prefix(&self, prefix: &str) {
            let mut rule_sets = self.inner.rule_sets.lock().unwrap();
            for rule_set in rule_sets.iter().filter(|r| r.probe_id().starts_with(prefix)) {
                rule_set.remove();
            }
            rule_sets.retain(|r| !r.probe_id().starts_with(prefix));
        }
        pub fn set_dispatcher(&self, dispatcher: Dispatcher) {
            *self.inner.dispatcher.lock().unwrap() = Some(dispatcher);
        }
        pub fn defer(&self, job: Deferred) {
            let host = self.clone();
            glib::idle_add_once(move || host.run(job));
        }
        fn run(&self, job: Deferred) {
            if let Deferred::Signal(probe, name, value) = job {
                if let Some(rule_set) = self.find(&probe) {
                    rule_set.signal(&name, value);
                }
            } else if let Some(dispatch) = self.inner.dispatcher.lock().unwrap().as_ref() {
                dispatch(job);
            } else {
                eprintln!("no pipeline to run a deferred action");
            }
        }
    }

    /// What triggered a rule: the pad, buffer or event, and the trigger value.
    pub struct Ctx<'a> {
        pub pad: Option<&'a gst::Pad>,
        pub buffer: Option<&'a gst::BufferRef>,
        pub value: Value,
        pub idle_ms: Option<u64>,
    }

    impl Ctx<'_> {
        pub fn new(value: Value) -> Self {
            Ctx { pad: None, buffer: None, value, idle_ms: None }
        }
    }

    /// Variables of a rule set.
    #[derive(Clone, Debug, Default)]
    pub struct Vars(BTreeMap<&'static str, Value>);

    impl Vars {
        pub fn new(initial: &[(&'static str, Value)]) -> Self {
            Vars(initial.iter().cloned().collect())
        }
        pub fn get(&self, name: &str) -> Value {
            self.0.get(name).cloned().unwrap_or(Value::Null)
        }
        pub fn set(&mut self, name: &'static str, value: Value) {
            self.0.insert(name, value);
        }
        pub fn increment(&mut self, name: &'static str, by: f64) {
            let next = self.get(name).number().unwrap_or(0.0) + by;
            self.set(
                name,
                if next.fract() == 0.0 { Value::Int(next as i64) } else { Value::Float(next) },
            );
        }
    }

    #[derive(Clone, Copy, Debug, PartialEq)]
    pub enum Verdict {
        Pass,
        Drop,
    }

    /// The rules of one rule set, generated as explicit code (see the `*Rules` types).
    pub trait Rules: Send + 'static {
        const NAME: &'static str;
        const IDLE: &'static [u64] = &[];
        const INTERVALS: &'static [u64] = &[];
        fn on_start(&mut self, _core: &Core, _ctx: &Ctx) {}
        fn on_buffer(&mut self, _core: &Core, _ctx: &Ctx) -> Verdict {
            Verdict::Pass
        }
        fn on_event(&mut self, _core: &Core, _ctx: &Ctx, _event: &str) -> Verdict {
            Verdict::Pass
        }
        fn on_idle(&mut self, _core: &Core, _ctx: &Ctx, _index: usize) {}
        fn on_resumed(&mut self, _core: &Core, _ctx: &Ctx) {}
        fn on_interval(&mut self, _core: &Core, _ctx: &Ctx, _index: usize) {}
        fn on_property(&mut self, _core: &Core, _ctx: &Ctx, _property: &str) -> bool {
            false
        }
        fn on_signal(&mut self, _core: &Core, _ctx: &Ctx, _name: &str) {}
    }

    #[derive(Default)]
    struct Track {
        started: Option<Instant>,
        last_buffer: Option<Instant>,
        idle_fired: Vec<bool>,
        last_pts: Option<u64>,
        gap_ms: Option<f64>,
        backwards: bool,
        arrivals: VecDeque<Instant>,
        counters: BTreeMap<String, u64>,
        seed: u64,
    }

    /// Watched pads, timers and the actions available to rules.
    pub struct Core {
        pub element: gst::Element,
        pub elements: Elements,
        pub probe_id: String,
        pub instance: String,
        pub node: String,
        pad_spec: Option<String>,
        host: Weak<HostInner>, // rule sets must not keep their host alive
        enabled: AtomicBool,
        pads: Mutex<Vec<gst::Pad>>,
        blocks: Mutex<Vec<(gst::Pad, gst::PadProbeId)>>,
        track: Mutex<Track>,
    }
"""
