"""Builds the exported pipeline without playing it and reports what the builders created."""

from _exported import load

exported = load()
pipeline = exported.ComponentsPipeline()
pipeline.build()
print("BUILT", len(pipeline.pipeline.children))
print("NESTED", pipeline.element("cam/inner/src").get_property("pattern").value_nick)
print("BUFFERS", pipeline.element("cam/inner/src").get_property("num-buffers"))
print("PORTS", pipeline.element("cam").get_static_pad("video") is not None)
