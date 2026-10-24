import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import { createScript } from "../../lib/scripts";
import { useGraphStore } from "../../store/graphStore";
import { useRecipeStore } from "../../store/recipeStore";
import { useRuntimeStore } from "../../store/runtimeStore";
import { node } from "../../test/fixtures";
import { ScriptsSection } from "./ScriptsSection";

const recipes = [
  { id: "keyframe-switch", name: "Switch on keyframe", description: "waits for a key unit", target_kind: "node" as const,
    factories: ["input-selector"], code: "def on_property(ctx, name, value):\n    return True\n" },
  { id: "gate", name: "Gate", description: "open/close", target_kind: "edge" as const, factories: [], code: "" },
];

describe("scripts section", () => {
  beforeEach(() => {
    useGraphStore.getState().load({ nodes: [node("sel", "input-selector")], edges: [] });
    useRuntimeStore.getState().reset();
    useRecipeStore.setState({ recipes: [], state: "idle", error: null });
    vi.spyOn(api, "scriptRecipes").mockResolvedValue(recipes);
  });
  afterEach(() => vi.restoreAllMocks());

  it("offers the keyframe switch on selectors and adds it in one click", async () => {
    render(<ScriptsSection target={{ kind: "node", id: "sel" }} factory="input-selector" selector />);
    fireEvent.click(screen.getByRole("button", { name: "Add the switch on keyframe script" }));
    await waitFor(() => expect(useGraphStore.getState().graph.scripts).toHaveLength(1));
    expect(screen.queryByRole("button", { name: "Add the switch on keyframe script" })).toBeNull();
    expect(screen.getByRole("button", { name: "Edit Switch on keyframe" })).toBeInTheDocument();
  });

  it("lists recipes for the target and opens the editor on add", async () => {
    render(<ScriptsSection target={{ kind: "node", id: "sel" }} factory="input-selector" />);
    fireEvent.click(screen.getByRole("button", { name: /add script/i }));
    const option = await screen.findByText("Switch on keyframe");
    expect(screen.queryByText("Gate")).toBeNull();
    fireEvent.click(option);
    expect(await screen.findByRole("dialog", { name: /script on sel/i })).toBeInTheDocument();
  });

  it("shows a trigger only for running scripts that define on_trigger", () => {
    const script = createScript({ kind: "node", id: "sel" }, "Tick", "def on_trigger(ctx, value):\n    pass\n");
    useGraphStore.getState().addScript(script);
    const { rerender } = render(<ScriptsSection target={{ kind: "node", id: "sel" }} />);
    expect(screen.getByRole("button", { name: /trigger/i })).toBeDisabled();
    useRuntimeStore.setState({ state: "playing" });
    rerender(<ScriptsSection target={{ kind: "node", id: "sel" }} />);
    expect(screen.getByRole("button", { name: /trigger/i })).toBeEnabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "Enable Tick" }));
    expect(useGraphStore.getState().graph.scripts?.[0].enabled).toBe(false);
    expect(screen.queryByRole("button", { name: /trigger/i })).toBeNull();
  });
});
