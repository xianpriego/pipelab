// Reference of the probe script API shown next to the editor.

const CALLBACKS: [string, string][] = [
  ["setup(ctx)", "Once, before the pipeline starts."],
  ["on_buffer(ctx, pad, buffer)", "Every buffer on the watched pads. Return DROP to drop it."],
  ["on_event(ctx, pad, event)", "Every downstream event (caps, segment, eos…) on the watched pads."],
  ["on_property(ctx, name, value)", "Element scripts: a live change requested from the UI. Return True if you handle it (it stays pending until the element reports it)."],
  ["on_trigger(ctx, value)", "The Trigger button of the inspector (value typed next to it, or None)."],
];

const CONTEXT: [string, string][] = [
  ["ctx.element / ctx.pad", "The element of an element script / the watched pad of a link script."],
  ["ctx.pipeline", "The Gst.Pipeline."],
  ["ctx.state", "A dict kept between calls."],
  ["ctx.get(name)", "Another element by name."],
  ["ctx.pad_named(name)", "A pad of ctx.element (e.g. \"sink_1\")."],
  ["ctx.log(message, **fields)", "Message in the Probe tab."],
  ["ctx.set(element, prop, value)", "Set a property (gst-launch syntax values)."],
  ["ctx.request_keyframe(pad=None)", "Send a force-key-unit event upstream."],
  ["ctx.is_keyframe(buffer)", "True when the buffer has no DELTA_UNIT flag."],
];

export function ScriptHelp() {
  return (
    <aside className="script-help" aria-label="Script API">
      <h4>Callbacks</h4>
      <p className="muted">All optional, at module level. Return <code>PASS</code> (default), <code>DROP</code> or <code>REMOVE</code>.</p>
      <dl>
        {CALLBACKS.map(([name, text]) => (
          <div key={name}><dt><code>{name}</code></dt><dd>{text}</dd></div>
        ))}
      </dl>
      <h4>Watched pads</h4>
      <p className="muted">
        Link scripts: the link&apos;s source pad. Element scripts: its sink pads; set <code>WATCH = &quot;src&quot;</code> or
        <code> &quot;all&quot;</code> to change it.
      </p>
      <h4>ctx</h4>
      <dl>
        {CONTEXT.map(([name, text]) => (
          <div key={name}><dt><code>{name}</code></dt><dd>{text}</dd></div>
        ))}
      </dl>
      <p className="muted"><code>Gst</code> and <code>GLib</code> are available. Scripts are exported in the Python program.</p>
    </aside>
  );
}
