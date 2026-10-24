// Builds the exported pipeline without playing it and reports what the builders created.
fn main() -> Result<()> {
    let pipeline = ComponentsPipeline::new()?;
    println!("BUILT {}", pipeline.pipeline().children().len());
    let source = pipeline.element("cam/inner/src")?;
    println!("NESTED {}", source.property_value("pattern").serialize()?);
    println!("BUFFERS {}", source.property::<i32>("num-buffers"));
    println!("PORTS {}", pipeline.element("cam")?.static_pad("video").is_some());
    Ok(())
}
