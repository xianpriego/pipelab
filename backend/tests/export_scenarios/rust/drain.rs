// Sink-port slot: removing a consumer drains it (EOS forwarded by the pipeline) before
// its request pad on the tee is released.
fn state(pipeline: &SinkPipeline) -> String {
    let ids: Vec<String> = pipeline.list_outputs().into_iter().map(|(id, _)| id).collect();
    let pads: Vec<String> = pipeline.element("split").unwrap().src_pads().iter().map(|p| p.name().to_string()).collect();
    format!("{} pads={}", ids.join(","), pads.join(","))
}

fn main() -> Result<()> {
    let pipeline = SinkPipeline::new(Config::default())?;
    let main_loop = glib::MainLoop::new(None, false);
    pipeline.start()?;
    let p = pipeline.clone();
    glib::timeout_add_once(Duration::from_millis(400), move || {
        println!("ADDED {}", p.add_output(TestConsumerParams::default()).unwrap());
        println!("STATE {}", state(&p));
    });
    let p = pipeline.clone();
    glib::timeout_add_once(Duration::from_millis(900), move || {
        p.remove_output("output0").unwrap();
        println!("REMOVING {}", state(&p));
    });
    let (p, quit) = (pipeline.clone(), main_loop.clone());
    glib::timeout_add_once(Duration::from_millis(1500), move || {
        println!("STATE {}", state(&p));
        quit.quit();
    });
    main_loop.run();
    pipeline.stop()
}
