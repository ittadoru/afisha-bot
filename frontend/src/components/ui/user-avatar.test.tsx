import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UserAvatar } from "./user-avatar";

const thumbnail = "/api/profiles/12345678/avatar?size=64&v=7";
const fallback = "/api/profiles/12345678/avatar?size=256&v=7";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("UserAvatar", () => {
  it("keeps a fast cached thumbnail visible", () => {
    vi.useFakeTimers();
    const { container } = render(
      <UserAvatar name="Анна" thumbnailUrl={thumbnail} fallbackUrl={fallback} />,
    );

    fireEvent.load(container.querySelector("img")!);
    act(() => vi.advanceTimersByTime(12_000));

    expect(container.querySelector("img")).toHaveClass("is-loaded");
    expect(container.querySelector("img")).toHaveAttribute("src", thumbnail);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("retries each size once before showing the unavailable state", () => {
    const { container } = render(
      <UserAvatar name="Анна" thumbnailUrl={thumbnail} fallbackUrl={fallback} />,
    );

    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toHaveAttribute(
      "src",
      `${thumbnail}&avatar_retry=1`,
    );
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toHaveAttribute("src", fallback);
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toHaveAttribute(
      "src",
      `${fallback}&avatar_retry=1`,
    );
    fireEvent.error(container.querySelector("img")!);

    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.querySelector(".user-avatar-unavailable")).toBeInTheDocument();
  });

  it("advances the same recovery chain after four-second timeouts", () => {
    vi.useFakeTimers();
    const { container } = render(
      <UserAvatar name="Анна" thumbnailUrl={thumbnail} fallbackUrl={fallback} />,
    );

    act(() => vi.advanceTimersByTime(4_000));
    expect(container.querySelector("img")).toHaveAttribute(
      "src",
      `${thumbnail}&avatar_retry=1`,
    );
    act(() => vi.advanceTimersByTime(4_000));
    expect(container.querySelector("img")).toHaveAttribute("src", fallback);
  });

  it("resets all attempts when the profile version changes", () => {
    const { container, rerender } = render(
      <UserAvatar name="Анна" thumbnailUrl={thumbnail} fallbackUrl={fallback} />,
    );
    fireEvent.error(container.querySelector("img")!);

    const nextThumbnail = thumbnail.replace("v=7", "v=8");
    rerender(
      <UserAvatar
        name="Анна"
        thumbnailUrl={nextThumbnail}
        fallbackUrl={fallback.replace("v=7", "v=8")}
      />,
    );

    expect(container.querySelector("img")).toHaveAttribute("src", nextThumbnail);
  });

  it("clears its timeout when unmounted", () => {
    vi.useFakeTimers();
    const { unmount } = render(
      <UserAvatar name="Анна" thumbnailUrl={thumbnail} fallbackUrl={fallback} />,
    );
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("does not start lazy attempts before entering the viewport", () => {
    vi.useFakeTimers();
    let intersectionCallback: IntersectionObserverCallback | null = null;
    class Observer {
      constructor(callback: IntersectionObserverCallback) {
        intersectionCallback = callback;
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal("IntersectionObserver", Observer);
    const { container } = render(
      <UserAvatar name="Анна" thumbnailUrl={thumbnail} fallbackUrl={fallback} />,
    );

    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(vi.getTimerCount()).toBe(0);
    act(() => {
      intersectionCallback?.(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });
    expect(container.querySelector("img")).toHaveAttribute("src", thumbnail);
    expect(vi.getTimerCount()).toBe(1);
  });

  it("uses initials only when the API reports no avatar URLs", () => {
    render(<UserAvatar name="Анна" />);
    expect(screen.getByText("А")).toBeInTheDocument();
  });
});
