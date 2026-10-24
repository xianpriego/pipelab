import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { Action, Condition } from "../../api/dynamic";
import { FALLBACK_SCHEMA } from "../../lib/probeSchema";
import { useGraphStore } from "../../store/graphStore";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useProjectStore } from "../../store/projectStore";
import { node } from "../../test/fixtures";
import { ActionList } from "./ActionList";
import { ConditionList } from "./ConditionList";
import { EMPTY_CONTEXT, RuleEditorCtx } from "./editorContext";
import { ProbeRuleList } from "./ProbeRuleList";
import { SpecForm } from "./SpecForm";

const ctx = { ...EMPTY_CONTEXT, variables: ["count"], nodes: ["sel"] };

function Harness<T>({ initial, render: view }: { initial: T; render: (value: T, set: (v: T) => void) => JSX.Element }) {
  const [value, setValue] = useState(initial);
  return (
    <RuleEditorCtx.Provider value={ctx}>
      {view(value, setValue)}
      <output data-testid="state">{JSON.stringify(value)}</output>
    </RuleEditorCtx.Provider>
  );
}

const state = () => JSON.parse(screen.getByTestId("state").textContent ?? "null") as unknown;

describe("schema-driven forms", () => {
  it("renders the fields of the chosen type and resets them on type change", () => {
    render(<Harness<Action> initial={{ type: "log", message: "hi" }} render={(value, set) => (
      <SpecForm specs={FALLBACK_SCHEMA.actions} item={value} onChange={set} label="Action" />
    )} />);
    expect(screen.getByLabelText("Message")).toHaveValue("hi");
    fireEvent.change(screen.getByLabelText("Action"), { target: { value: "set-property" } });
    expect(state()).toEqual({ type: "set-property" });
    expect(screen.getByLabelText("Element")).toBeInTheDocument();
    expect(screen.getByLabelText("Property")).toBeInTheDocument();
  });

  it("types numbers and offers $ references in value fields", () => {
    render(<Harness<Condition> initial={{ type: "variable", name: "count", op: ">", value: 1 }} render={(value, set) => (
      <SpecForm specs={FALLBACK_SCHEMA.conditions} item={value} onChange={set} label="Condition" />
    )} />);
    const input = screen.getByLabelText("Value");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "$c" } });
    fireEvent.click(screen.getByRole("option", { name: /\$count/ }));
    expect(state()).toMatchObject({ value: "$count" });
    fireEvent.change(input, { target: { value: "25" } });
    expect(state()).toMatchObject({ value: 25 });
  });
});

describe("rule lists", () => {
  it("adds, reorders and removes actions", () => {
    render(<Harness<Action[]> initial={[{ type: "drop" }, { type: "log", message: "x" }]} render={(value, set) => (
      <ActionList actions={value} onChange={set} label="Rule 1" />
    )} />);
    fireEvent.click(screen.getByRole("button", { name: "Move Rule 1 action 2 up" }));
    expect((state() as Action[]).map((a) => a.type)).toEqual(["log", "drop"]);
    fireEvent.click(screen.getByRole("button", { name: "Action" }));
    expect((state() as Action[]).length).toBe(3);
    fireEvent.click(screen.getByRole("button", { name: "Remove Rule 1 action 1" }));
    expect((state() as Action[]).map((a) => a.type)).toEqual(["drop", "log"]);
  });

  it("negates conditions", () => {
    render(<Harness<Condition[]> initial={[{ type: "keyframe" }]} render={(value, set) => (
      <ConditionList conditions={value} onChange={set} label="Rule 1" />
    )} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Negate Rule 1 condition 1" }));
    expect(state()).toEqual([{ type: "keyframe", negate: true }]);
  });
});

describe("probe list", () => {
  beforeEach(() => {
    useGraphStore.getState().load({ nodes: [node("src", "videotestsrc"), node("sink", "fakesink")], edges: [
      { id: "e1", source: "src", source_pad: "src", target: "sink", target_pad: "sink" },
    ] });
    useRuntimeStore.getState().reset();
    vi.spyOn(api, "probeSchema").mockResolvedValue(FALLBACK_SCHEMA);
  });
  afterEach(() => vi.restoreAllMocks());

  it("adds a probe from a template, edits it and sends signals while running", async () => {
    useProjectStore.setState({ meta: { id: "p1" } as never });
    const signal = vi.spyOn(api, "runtimeSignal").mockResolvedValue({ ok: true, error: null } as never);
    render(<ProbeRuleList target={{ kind: "edge", id: "e1" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add probe" }));
    expect(screen.queryByText("Keyframe switch")).toBeNull();
    fireEvent.click(screen.getByText("Gate"));
    const dialog = await screen.findByRole("dialog", { name: /probe on/i });
    fireEvent.change(screen.getAllByRole("textbox", { name: "Name" })[0], { target: { value: "Door" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    const probes = useGraphStore.getState().graph.probes ?? [];
    expect(probes.map((p) => p.name)).toEqual(["Door"]);

    expect(screen.getByRole("button", { name: "Send signal open to Door" })).toBeDisabled();
    useRuntimeStore.setState({ state: "playing" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Send signal open to Door" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Send signal open to Door" }));
    await waitFor(() => expect(signal).toHaveBeenCalledWith("p1", probes[0].id, "open", null));
  });
});
