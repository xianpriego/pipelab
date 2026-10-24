import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { FlowToggle } from "../editor/FlowToggle";
import { useUiStore } from "../store/uiStore";
import { ThemeToggle } from "./ThemeToggle";

describe("toggles", () => {
  beforeEach(() => {
    localStorage.clear();
    useUiStore.setState({ theme: "dark", flowAnimation: true });
  });

  it("switches and remembers the theme", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Toggle theme" }));
    expect(useUiStore.getState().theme).toBe("light");
    expect(localStorage.getItem("pipelab.theme")).toBe("light");
  });

  it("switches and remembers the buffer flow animation", () => {
    render(<FlowToggle />);
    const button = screen.getByRole("button", { name: "Buffer flow animation" });
    expect(button).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(button);
    expect(useUiStore.getState().flowAnimation).toBe(false);
    expect(localStorage.getItem("pipelab.flowAnimation")).toBe("off");
  });
});
