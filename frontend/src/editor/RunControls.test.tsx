import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useRuntimeStore } from "../store/runtimeStore";
import { RunControls } from "./RunControls";

const setState = (state: Parameters<ReturnType<typeof useRuntimeStore.getState>["setStatus"]>[0]["state"]) =>
  useRuntimeStore.getState().setStatus({ project_id: "p", state, started_at: null, error: null });

describe("RunControls", () => {
  beforeEach(() => useRuntimeStore.getState().reset());

  it("only allows play when idle", () => {
    render(<RunControls />);
    expect(screen.getByLabelText("Play")).toBeEnabled();
    expect(screen.getByLabelText("Pause")).toBeDisabled();
    expect(screen.getByLabelText("Stop")).toBeDisabled();
    expect(screen.getByLabelText("Kill")).toBeDisabled();
  });

  it("allows pause, stop and kill while playing", () => {
    setState("playing");
    render(<RunControls />);
    expect(screen.getByLabelText("Play")).toBeDisabled();
    expect(screen.getByLabelText("Pause")).toBeEnabled();
    expect(screen.getByLabelText("Stop")).toBeEnabled();
  });

  it("keeps the errored worker stoppable and restartable", () => {
    setState("error");
    render(<RunControls />);
    expect(screen.getByLabelText("Play")).toBeEnabled();
    expect(screen.getByLabelText("Stop")).toBeEnabled();
    expect(screen.getByLabelText("Kill")).toBeEnabled();
    expect(screen.getByText("error")).toBeInTheDocument();
  });
});
