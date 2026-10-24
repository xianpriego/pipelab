"""Builds the kitchen-sink pipeline without playing it: every construction path runs."""

from _exported import load

exported = load()
pipeline = exported.KitchenPipeline()
pipeline.build()
print("BUILT", len(pipeline.pipeline.children), len(pipeline.list_extras()))
print("NESTED", pipeline.element("cam/inner/src").get_property("pattern").value_nick)
