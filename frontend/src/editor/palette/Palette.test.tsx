import { fireEvent, render as renderUi, screen, within } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { useCatalogStore } from "../../store/catalogStore";
import { summary } from "../../test/fixtures";
import { Palette } from "./Palette";

const render = (ui: ReactElement) => renderUi(<ReactFlowProvider>{ui}</ReactFlowProvider>);

const elements = [
  summary("videotestsrc", { categories: ["source", "video"], long_name: "Video test source" }),
  summary("udpsrc", { categories: ["network", "source"] }),
  summary("nvh264enc", { categories: ["encoder", "hardware", "video"], long_name: "NVENC H.264 Encoder" }),
  summary("fakesink", { categories: ["sink"] }),
];

describe("palette", () => {
  beforeEach(() => {
    localStorage.clear();
    useCatalogStore.setState({
      elements, byName: Object.fromEntries(elements.map((e) => [e.name, e])), state: "ready",
    });
  });

  it("groups elements in collapsible categories with counts", () => {
    render(<Palette />);
    const sources = screen.getByRole("button", { name: /Sources/ });
    expect(sources).toHaveAttribute("aria-expanded", "false");
    expect(within(sources).getByText("2")).toBeInTheDocument();
    fireEvent.click(sources);
    expect(sources).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByText("udpsrc").length).toBeGreaterThan(0);
    expect(localStorage.getItem("pipelab.palette.expanded")).toBe('["sources"]');
  });

  it("shows search matches grouped and expanded, with a GPU badge for hardware", () => {
    render(<Palette />);
    fireEvent.change(screen.getByLabelText("Search elements"), { target: { value: "h264 enc" } });
    expect(screen.getByRole("button", { name: /Encoders/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("GPU")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sources/ })).toBeNull();
  });
});
