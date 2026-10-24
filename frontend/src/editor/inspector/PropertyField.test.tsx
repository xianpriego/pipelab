import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { prop } from "../../test/fixtures";
import { PropertyField } from "./PropertyField";

function renderField(p: ReturnType<typeof prop>, value?: string | number | boolean, running = false) {
  const onChange = vi.fn();
  const onTryLive = vi.fn();
  render(<PropertyField prop={p} value={value} running={running} pads={["sink_0", "sink_1"]} onChange={onChange}
    onTryLive={onTryLive} />);
  return { onChange, onTryLive };
}

describe("PropertyField", () => {
  it("toggles booleans", () => {
    const { onChange } = renderField(prop("is-live", { type: "boolean", default: false }));
    fireEvent.click(screen.getByLabelText("is-live"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("commits valid numbers on blur and rejects out of range values", () => {
    const { onChange } = renderField(prop("num-buffers", { type: "int", minimum: -1, maximum: 1000, default: -1 }));
    const input = screen.getByLabelText("num-buffers");
    fireEvent.change(input, { target: { value: "5000" } });
    fireEvent.blur(input);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Maximum is 1000")).toBeInTheDocument();
    fireEvent.change(input, { target: { value: "300" } });
    fireEvent.blur(input);
    expect(onChange).toHaveBeenCalledWith(300);
  });

  it("renders a slider for bounded ranges", () => {
    const { onChange } = renderField(prop("alpha", { type: "double", minimum: 0, maximum: 1, default: 1 }));
    fireEvent.change(screen.getByLabelText("alpha slider"), { target: { value: "0.25" } });
    expect(onChange).toHaveBeenCalledWith(0.25);
  });

  it("selects enum values by nick", () => {
    const { onChange } = renderField(prop("pattern", {
      type: "enum", value_type: "GstVideoTestSrcPattern", default: "smpte",
      enum_values: [{ value: 0, nick: "smpte", name: "SMPTE" }, { value: 18, nick: "ball", name: "Ball" }],
    }));
    fireEvent.change(screen.getByLabelText("pattern"), { target: { value: "ball" } });
    expect(onChange).toHaveBeenCalledWith("ball");
  });

  it("joins flags with +", () => {
    const { onChange } = renderField(prop("flags", {
      type: "flags", default: "a",
      enum_values: [{ value: 1, nick: "a", name: "A" }, { value: 2, nick: "b", name: "B" }],
    }), "a");
    fireEvent.click(screen.getByLabelText("b"));
    expect(onChange).toHaveBeenCalledWith("a+b");
  });

  it("lists pads for GstPad properties", () => {
    const { onChange } = renderField(prop("active-pad", { type: "pad", value_type: "GstPad" }));
    fireEvent.change(screen.getByLabelText("active-pad"), { target: { value: "sink_1" } });
    expect(onChange).toHaveBeenCalledWith("sink_1");
  });

  it("resets modified values", () => {
    const { onChange } = renderField(prop("location"), "out.mp4");
    fireEvent.click(screen.getByLabelText("Reset location"));
    expect(onChange).toHaveBeenCalledWith(undefined);
  });

  it("shows live / restart affordances while running", () => {
    renderField(prop("volume", { type: "double", mutable: "playing" }), undefined, true);
    expect(screen.getByText("live")).toBeInTheDocument();
  });

  it("offers 'try live' for undeclared mutability while running", () => {
    const { onTryLive } = renderField(prop("pattern", { mutable: "unknown" }), undefined, true);
    fireEvent.click(screen.getByText("try live"));
    expect(onTryLive).toHaveBeenCalled();
  });

  it("marks properties that need a restart", () => {
    renderField(prop("device", { mutable: "ready" }), undefined, true);
    expect(screen.getByText("restart")).toBeInTheDocument();
  });
});
