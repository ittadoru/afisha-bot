import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UserAvatar } from "./user-avatar";

describe("UserAvatar", () => {
  it("falls back from the thumbnail to the full avatar without showing initials", () => {
    const { container } = render(
      <UserAvatar
        name="Анна"
        thumbnailUrl="/avatar-64.webp"
        fallbackUrl="/avatar-256.webp"
      />,
    );

    const thumbnail = container.querySelector("img");
    expect(thumbnail).toHaveAttribute("src", "/avatar-64.webp");
    expect(container.querySelector(".user-avatar-initial")).not.toBeInTheDocument();

    fireEvent.error(thumbnail!);
    const fallback = container.querySelector("img");
    expect(fallback).toHaveAttribute("src", "/avatar-256.webp");

    fireEvent.error(fallback!);
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.querySelector(".user-avatar-unavailable")).toBeInTheDocument();
  });

  it("uses initials only when the API reports no avatar URLs", () => {
    render(<UserAvatar name="Анна" />);
    expect(screen.getByText("А")).toBeInTheDocument();
  });
});
