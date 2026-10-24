// Builds the kitchen-sink pipeline without playing it: every construction path runs.
fn main() -> Result<()> {
    let pipeline = KitchenPipeline::new(Config::default())?;
    let children = pipeline.pipeline().children().len();
    println!("BUILT {children} {}", pipeline.list_extras().len());
    let pattern = pipeline.element("cam/inner/src")?.property_value("pattern");
    println!("NESTED {}", pattern.serialize()?);
    Ok(())
}
