import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../api/client";
import type { ComponentBundle } from "../../api/dynamic";
import { useComponentStore } from "../../store/componentStore";
import { importComponentFile } from "./componentActions";
import { StartersDialog } from "./StartersDialog";

const bundle: ComponentBundle = {
  format: "pipelab-components", version: 1,
  components: [{ id: "cam", name: "Cam", description: "", version: 3, graph: { nodes: [], edges: [] }, ports: [], parameters: [] }],
};

const file = (content: string) => new File([content], "cam.pipelab-component.json", { type: "application/json" });

describe("component files and starters", () => {
  beforeEach(() => {
    vi.spyOn(api, "listComponents").mockResolvedValue([]);
    vi.spyOn(api, "catalog").mockResolvedValue([]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });
  afterEach(() => vi.restoreAllMocks());

  it("imports a file, asking before replacing components with the same id", async () => {
    const importer = vi.spyOn(api, "importComponents")
      .mockRejectedValueOnce(new ApiError(409, "already in the library: cam"))
      .mockResolvedValueOnce({ imported: ["cam"] });
    expect(await importComponentFile(file(JSON.stringify(bundle)))).toBe(true);
    expect(importer.mock.calls.map((call) => call[1])).toEqual([undefined, true]);
    expect(vi.mocked(window.confirm).mock.calls[0][0]).toContain("cam");
  });

  it("rejects files that are not component files", async () => {
    const importer = vi.spyOn(api, "importComponents");
    expect(await importComponentFile(file('{"nodes": []}'))).toBe(false);
    expect(await importComponentFile(file("not json"))).toBe(false);
    expect(importer).not.toHaveBeenCalled();
  });

  it("lists starters, flags missing elements and adds one to the library", async () => {
    useComponentStore.setState({ library: [] });
    vi.spyOn(api, "listStarters").mockResolvedValue([
      { id: "h264-encoder", name: "H.264 encoder", description: "x264", available: true, missing: [] },
      { id: "h264-encoder-nvidia", name: "H.264 encoder (NVIDIA)", description: "nvenc", available: false, missing: ["nvh264enc"] },
    ]);
    const install = vi.spyOn(api, "installStarter").mockResolvedValue(bundle.components[0]);
    render(<StartersDialog onClose={() => undefined} />);
    expect(await screen.findByText(/Not installed here: nvh264enc/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add H.264 encoder" }));
    await waitFor(() => expect(install).toHaveBeenCalledWith("h264-encoder"));
  });
});
