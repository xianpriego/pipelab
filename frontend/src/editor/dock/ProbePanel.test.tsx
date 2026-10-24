import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useGraphStore } from "../../store/graphStore";
import { useProbeStore } from "../../store/probeStore";
import { node } from "../../test/fixtures";
import { ProbePanel } from "./ProbePanel";

const buffer = (time: number, flags: string[]) => ({
  kind: "buffer" as const, time, pts: time, dts: null, duration: 0.033, size: 2048, flags, offset: null,
});

describe("probe panel", () => {
  beforeEach(() => {
    useProbeStore.getState().reset();
    useGraphStore.getState().load({
      nodes: [node("enc", "x264enc"), node("pay", "rtph264pay")],
      edges: [{ id: "e1", source: "enc", source_pad: "src", target: "pay", target_pad: "sink" }],
    });
  });

  it("explains how to probe when nothing is probed", () => {
    render(<ProbePanel />);
    expect(screen.getByText(/Probe a link while the pipeline runs/)).toBeInTheDocument();
  });

  it("lists buffers and events, marks key units and pauses", () => {
    useProbeStore.getState().setProbed("e1", true);
    useProbeStore.getState().ingest({
      type: "probe", edge_id: "e1", dropped: 0,
      items: [
        { kind: "event", time: 0, event: "caps", detail: "video/x-h264" },
        buffer(0.1, []),
        buffer(0.133, ["delta-unit"]),
      ],
    });
    const { container } = render(<ProbePanel />);
    expect(container.querySelectorAll("tr.probe-row")).toHaveLength(3);
    expect(container.querySelectorAll("tr.probe-row.key")).toHaveLength(1);
    expect(screen.getAllByText("enc.src → pay.sink").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(useProbeStore.getState().paused).toBe(true);
    fireEvent.change(screen.getByLabelText("Item kind"), { target: { value: "event" } });
    expect(container.querySelectorAll("tr.probe-row")).toHaveLength(1);
  });
});

describe("probe panel script rows", () => {
  beforeEach(() => {
    useProbeStore.getState().reset();
    useGraphStore.getState().load({
      nodes: [node("sel", "input-selector")], edges: [],
      scripts: [{ id: "s1", name: "Switch on keyframe", enabled: true, target: { kind: "node", id: "sel" }, code: "" }],
    });
  });

  it("lists script messages under the element they run on", () => {
    useProbeStore.getState().ingestScript({
      type: "script", script_id: "s1", name: "Switch on keyframe", level: "info",
      message: "switched to sink_1 at keyframe", time: 2,
    });
    const { container } = render(<ProbePanel />);
    expect(container.querySelectorAll("tr.probe-row.log")).toHaveLength(1);
    expect(screen.getByText("switched to sink_1 at keyframe")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Item kind"), { target: { value: "buffer" } });
    expect(container.querySelectorAll("tr.probe-row")).toHaveLength(0);
  });
});
