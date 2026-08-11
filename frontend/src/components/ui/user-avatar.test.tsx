import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UserAvatar } from "./user-avatar";

describe("UserAvatar", () => {
  it("falls back from the thumbnail to the full avatar without showing initials", () => {
    const { container } = render(
      <UserAvatar
        name="Анна"
        thumbnailUrl="/api/profiles/12345678/avatar?size=64&v=7"
        fallbackUrl="/api/profiles/12345678/avatar?size=256&v=7"
      />,
    );

    const thumbnail = container.querySelector("img");
    expect(thumbnail).toHaveAttribute(
      "src",
      "/api/profiles/12345678/avatar?size=64&v=7",
    );
    expect(container.querySelector(".user-avatar-initial")).not.toBeInTheDocument();

    fireEvent.load(thumbnail!);
    expect(container.querySelector("img")).toHaveClass("is-loaded");
    expect(container.querySelector("img")).toHaveAttribute("src", expect.stringContaining("size=64"));

    fireEvent.error(thumbnail!);
    const fallback = container.querySelector("img");
    expect(fallback).toHaveAttribute(
      "src",
      "/api/profiles/12345678/avatar?size=256&v=7",
    );

    fireEvent.error(fallback!);
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.querySelector(".user-avatar-unavailable")).toBeInTheDocument();
  });

  it("uses initials only when the API reports no avatar URLs", () => {
    render(<UserAvatar name="Анна" />);
    expect(screen.getByText("А")).toBeInTheDocument();
  });
});
