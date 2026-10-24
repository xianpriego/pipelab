// Scenario 1: the source of the `cam` instance stops after 20 buffers; its watchdog
// rule set posts "branch-down" with `$instance` once 500 ms pass without buffers.
fn main() -> Result<()> {
    let pipeline = WatchdogPipeline::new(Config::default())?;
    pipeline.connect_message(|message| {
        let (input, idle) = (message.field("input"), message.field("idle_ms"));
        println!("MESSAGE {} input={} idle_ms={}", message.name, input.as_string(), idle.as_string());
    });
    let main_loop = glib::MainLoop::new(None, false);
    let quit = main_loop.clone();
    glib::timeout_add_once(Duration::from_millis(2500), move || quit.quit());
    pipeline.start()?;
    main_loop.run();
    pipeline.stop()
}
