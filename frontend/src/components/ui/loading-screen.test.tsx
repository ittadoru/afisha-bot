import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LoadingScreen } from "./loading-screen";
import { TextBlink } from "./text-blink";

afterEach(cleanup);

describe("LoadingScreen", () => {
  it("uses the fixed Avar loading text and accessible status semantics", () => {
    render(<LoadingScreen variant="section" className="custom-loader" />);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Ургъула…");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveClass("loading-screen--section", "custom-loader");
  });

  it.each(["screen", "section", "overlay"] as const)("supports the %s placement variant", (variant) => {
    render(<LoadingScreen variant={variant} />);
    expect(screen.getByRole("status")).toHaveClass(`loading-screen--${variant}`);
  });
});

describe("TextBlink", () => {
  it("adds the shared animation class while preserving the selected element", () => {
    render(<TextBlink as="span" className="custom-text">Ургъула…</TextBlink>);

    const text = screen.getByText("Ургъула…");
    expect(text.tagName).toBe("SPAN");
    expect(text).toHaveClass("text-blink", "custom-text");
    expect(text).toHaveStyle({ animation: "loading-ui-text-blink var(--duration, 2s) ease-in-out infinite" });
  });
});
