"""Fixed parts of the Rust pipeline type (``PIPELINE`` is replaced by its name)."""

STATE = """
type MessageCallback = Arc<dyn Fn(&rt::AppMessage) + Send + Sync>;

struct Inner {
    pipeline: gst::Pipeline,
    elements: Elements,
    host: ProbeHost,
    SLOTS_FIELD    callbacks: Mutex<Vec<MessageCallback>>,
    started: Mutex<Option<Instant>>,
    watch: Mutex<Option<gst::bus::BusWatchGuard>>,
    main_loop: Mutex<Option<glib::MainLoop>>,
    error: Mutex<Option<String>>,
}

/// NAME: owns the pipeline, its dynamic parts and the bus (cheap to clone).
#[derive(Clone)]
pub struct PIPELINE {
    inner: Arc<Inner>,
}
"""

LIFECYCLE = """
impl PIPELINE {
    /// The underlying GstPipeline.
    pub fn pipeline(&self) -> &gst::Pipeline {
        &self.inner.pipeline
    }

    /// An element by name, or `instance/inner` inside component instances.
    pub fn element(&self, path: &str) -> Result<gst::Element> {
        rt::find_element(&self.inner.pipeline, &self.inner.elements, path)
    }

    /// Sets the pipeline to PLAYING; the default GLib main context must run (see `run()`).
    pub fn start(&self) -> Result<()> {
        let mut watch = self.inner.watch.lock().unwrap();
        if watch.is_none() {
            let weak = Arc::downgrade(&self.inner);
            let bus = self.inner.pipeline.bus().context("the pipeline has no bus")?;
            *watch = Some(bus.add_watch(move |_, message| {
                if let Some(inner) = weak.upgrade() {
                    PIPELINE { inner }.on_bus(message);
                }
                glib::ControlFlow::Continue
            })?);
        }
        drop(watch);
        self.inner.pipeline.set_state(gst::State::Playing).context("the pipeline refused to start")?;
        Ok(())
    }

    pub fn stop(&self) -> Result<()> {
        self.inner.pipeline.set_state(gst::State::Null)?;
        self.inner.watch.lock().unwrap().take();
        Ok(())
    }

    /// Asks the sources to finish so muxers and files are finalised cleanly.
    pub fn send_eos(&self) {
        self.inner.pipeline.send_event(gst::event::Eos::new());
    }

    /// `callback` receives every application message (probe rules, API functions).
    pub fn connect_message<F: Fn(&rt::AppMessage) + Send + Sync + 'static>(&self, callback: F) {
        self.inner.callbacks.lock().unwrap().push(Arc::new(callback));
    }

    /// Changes a property; probe rules on that element may intercept it (returns `true`).
    pub fn set_element_property(&self, element: &str, property: &str, value: &Value) -> Result<bool> {
        if self.inner.host.rule_sets().iter().any(|r| r.offer_property(element, property, value)) {
            return Ok(true);
        }
        rt::apply_value(&self.element(element)?, property, value, None)?;
        Ok(false)
    }

    /// Fires the `signal` rules of a probe rule set (`<instance>/<probe>` inside components).
    pub fn signal(&self, probe: &str, name: &str, value: Value) -> Result<()> {
        let rule_set = self.inner.host.find(probe).ok_or_else(|| anyhow!("no probe {probe}"))?;
        rule_set.signal(name, value);
        Ok(())
    }

    /// Plays until end-of-stream or an error (call `send_eos()` to finish early).
    pub fn run(&self) -> Result<()> {
        let main_loop = glib::MainLoop::new(None, false);
        *self.inner.main_loop.lock().unwrap() = Some(main_loop.clone());
        self.start()?;
        main_loop.run();
        self.stop()?;
        match self.inner.error.lock().unwrap().take() {
            Some(error) => Err(anyhow!(error)),
            None => Ok(()),
        }
    }

    fn elapsed(&self) -> f64 {
        self.inner.started.lock().unwrap().map_or(0.0, |t| t.elapsed().as_secs_f64())
    }

    fn post(&self, name: &str, fields: Vec<(&str, Value)>) {
        let pipeline = &self.inner.pipeline;
        let message = gst::message::Application::builder(rt::structure(name, &fields)).src(pipeline).build();
        let _ = pipeline.post_message(message);
    }

    fn on_bus(&self, message: &gst::Message) {
        use gst::MessageView;
        match message.view() {
            MessageView::Application(application) => {
                let Some(structure) = application.structure() else { return };
                let received = rt::AppMessage::new(structure, message.src());
                let callbacks = self.inner.callbacks.lock().unwrap().clone();
                for callback in callbacks {
                    callback(&received);
                }
            }
            MessageView::StateChanged(change) => {
                let from_pipeline = message.src() == Some(self.inner.pipeline.upcast_ref::<gst::Object>());
                if from_pipeline && change.current() == gst::State::Playing && !self.inner.host.started() {
                    *self.inner.started.lock().unwrap() = Some(Instant::now());
                    self.inner.host.start();
                }
            }
            MessageView::Element(element) => {
                let forwarded = element
                    .structure()
                    .filter(|s| s.has_name("GstBinForwarded"))
                    .and_then(|s| s.get::<gst::Message>("message").ok());
                if let Some(forwarded) = forwarded {
                    if let (MessageView::Eos(_), Some(source)) = (forwarded.view(), forwarded.src()) {
                        self.finish_drained(source);
                    }
                }
            }
            MessageView::Error(error) => {
                let source = message.src().map(|s| s.path_string().to_string()).unwrap_or_default();
                let text = format!("{source}: {} ({:?})", error.error(), error.debug());
                eprintln!("ERROR from {text}");
                *self.inner.error.lock().unwrap() = Some(text);
                self.quit();
            }
            MessageView::Eos(_) => self.quit(),
            _ => {}
        }
    }

    fn quit(&self) {
        if let Some(main_loop) = self.inner.main_loop.lock().unwrap().as_ref() {
            main_loop.quit();
        }
    }
}
"""
