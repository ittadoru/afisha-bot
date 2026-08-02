import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("landing", () => {
  it("shows the accepted headline and main action", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /Есть куда пойти/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ехала →" })).toBeInTheDocument();
  });
});
