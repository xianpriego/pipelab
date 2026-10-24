// Scenario 4: an active-pad change is intercepted and applied on the next keyframe.
fn active(pipeline: &SwitchPipeline) -> String {
    let pad = pipeline.element("sel").unwrap().property::<Option<gst::Pad>>("active-pad");
    pad.map(|p| p.name().to_string()).unwrap_or_default()
}

fn main() -> Result<()> {
    let pipeline = SwitchPipeline::new(Config::default())?;
    pipeline.connect_message(|message| println!("MESSAGE {} pad={}", message.name, message.field("pad").as_string()));
    let main_loop = glib::MainLoop::new(None, false);
    pipeline.start()?;
    let p = pipeline.clone();
    glib::timeout_add_once(Duration::from_millis(1000), move || {
        let intercepted = p.set_element_property("sel", "active-pad", &Value::from("sink_1")).unwrap();
        println!("INTERCEPTED {intercepted}");
        println!("ACTIVE {}", active(&p));
    });
    let (p, quit) = (pipeline.clone(), main_loop.clone());
    glib::timeout_add_once(Duration::from_millis(3000), move || {
        println!("ACTIVE {}", active(&p));
        quit.quit();
    });
    main_loop.run();
    pipeline.stop()
}
