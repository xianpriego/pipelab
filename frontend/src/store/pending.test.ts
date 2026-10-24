import { beforeEach, describe, expect, it } from "vitest";
import { useRuntimeStore } from "./runtimeStore";

const runtimeEvent = (value: string, origin: "runtime" | "user" = "runtime") => ({
  type: "property" as const, node_id: "sel", property: "active-pad", value, ok: true, error: null, origin,
});

describe("deferred property changes", () => {
  beforeEach(() => useRuntimeStore.getState().reset());

  it("stay pending until the element reports a value by itself", () => {
    useRuntimeStore.getState().setPending("sel", "active-pad", "sink_1");
    useRuntimeStore.getState().apply(runtimeEvent("sink_1", "user"));
    expect(useRuntimeStore.getState().pending.sel["active-pad"]).toBe("sink_1");
    useRuntimeStore.getState().apply(runtimeEvent("sink_1"));
    expect(useRuntimeStore.getState().pending).toEqual({});
    expect(useRuntimeStore.getState().liveProps.sel["active-pad"]).toBe("sink_1");
  });

  it("are keyed by pad for pad properties and dropped on a new run", () => {
    const store = useRuntimeStore.getState();
    store.setPending("mix", "xpos", 10, "sink_1");
    expect(useRuntimeStore.getState().pending.mix["sink_1::xpos"]).toBe(10);
    useRuntimeStore.getState().apply({ type: "state", state: "starting" });
    expect(useRuntimeStore.getState().pending).toEqual({});
  });

  it("ignore the deferred echo of the request, which still carries the old value", () => {
    useRuntimeStore.setState({ liveProps: { sel: { "active-pad": "sink_0" } } });
    useRuntimeStore.getState().apply({ ...runtimeEvent("sink_0", "user"), deferred: true });
    useRuntimeStore.getState().apply({ ...runtimeEvent("sink_9", "user"), deferred: true });
    expect(useRuntimeStore.getState().liveProps.sel["active-pad"]).toBe("sink_0");
  });

  it("can be cancelled explicitly", () => {
    useRuntimeStore.getState().setPending("sel", "active-pad", "sink_1");
    useRuntimeStore.getState().setPending("sel", "active-pad", undefined);
    expect(useRuntimeStore.getState().pending).toEqual({});
  });
});
