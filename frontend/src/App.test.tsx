import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("@/components/event-map", () => ({
  EventMap: () => <section aria-label="Карта событий" />,
}));

describe("landing", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
  });

  it("shows the accepted headline and main action", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /Есть куда пойти/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ехала →" })).toHaveAttribute("href", "/app");
    expect(screen.getByRole("link", { name: "Открыть карту" })).toHaveAttribute("href", "/app");
  });

  it("opens the map directly at /app", async () => {
    window.history.replaceState({}, "", "/app");

    render(<App />);

    expect(await screen.findByLabelText("Карта событий")).toBeInTheDocument();
  });
});
