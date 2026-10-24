// Scenario 2: one initial tile, two added while running, one removed and one restarted.
fn ids(pipeline: &SlotsPipeline) -> String {
    pipeline.list_tiles().into_iter().map(|(id, _)| id).collect::<Vec<_>>().join(",")
}

fn main() -> Result<()> {
    let pipeline = SlotsPipeline::new(Config::default())?;
    let main_loop = glib::MainLoop::new(None, false);
    pipeline.start()?;
    let p = pipeline.clone();
    glib::timeout_add_once(Duration::from_millis(500), move || {
        let first = p.add_tile(TestTileParams { pattern: Some("snow".into()) }).unwrap();
        let second = p.add_tile(TestTileParams::default()).unwrap();
        println!("ADDED {first} {second}");
    });
    let p = pipeline.clone();
    glib::timeout_add_once(Duration::from_millis(1200), move || {
        println!("LIST {}", ids(&p));
        p.remove_tile("tile1").unwrap();
        println!("LIST {}", ids(&p));
    });
    let p = pipeline.clone();
    glib::timeout_add_once(Duration::from_millis(1700), move || {
        println!("RESTART {}", p.restart_tile("tile2").unwrap());
    });
    let (p, quit) = (pipeline.clone(), main_loop.clone());
    glib::timeout_add_once(Duration::from_millis(2500), move || {
        let (_, state, _) = p.pipeline().state(gst::ClockTime::ZERO);
        println!("FINAL {} {state:?}", ids(&p));
        let pads: Vec<String> = p.element("mix").unwrap().sink_pads().iter().map(|pad| pad.name().to_string()).collect();
        println!("PADS {}", pads.join(","));
        quit.quit();
    });
    main_loop.run();
    pipeline.stop()
}
