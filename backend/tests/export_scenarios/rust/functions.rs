// Scenario 3: the `configure` API function sets a property and posts a message.
fn main() -> Result<()> {
    let pipeline = FunctionsPipeline::new(Config::default())?;
    pipeline.connect_message(|message| {
        println!("MESSAGE {} pattern={} source={:?}", message.name, message.field("pattern").as_string(), message.source);
    });
    let main_loop = glib::MainLoop::new(None, false);
    pipeline.start()?;
    let p = pipeline.clone();
    glib::timeout_add_once(Duration::from_millis(500), move || {
        p.configure("snow").unwrap();
        let pattern = p.element("src").unwrap().property_value("pattern");
        println!("PATTERN {}", pattern.serialize().unwrap());
    });
    let quit = main_loop.clone();
    glib::timeout_add_once(Duration::from_millis(1200), move || quit.quit());
    main_loop.run();
    pipeline.stop()
}
