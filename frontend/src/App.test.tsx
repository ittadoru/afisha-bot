import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("@/components/event-map", () => ({
  EventMap: () => <section aria-label="Карта событий" />,
}));

afterEach(cleanup);

const profile = {
  public_id: "12345678",
  display_name: "Гость 2048",
  bio: null,
  selected_city_id: null,
  age_confirmed: true,
};

beforeEach(() => {
  window.Telegram = {
    WebApp: {
      initData: "signed-init-data",
      ready: vi.fn(),
      expand: vi.fn(),
    },
  };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(profile), {
    status: 200,
    headers: { "Content-Type": "application/json", "X-Afisha-CSRF": "csrf-token" },
  })));
});

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
    expect(screen.getByRole("navigation", { name: "Основные разделы" })).toBeInTheDocument();
  });

  it("allows visiting every future Mini App section", async () => {
    window.history.replaceState({}, "", "/app");
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Ищу людей" }));
    expect(screen.getByRole("heading", { name: "Найдите компанию" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Создать" }));
    expect(screen.getByRole("heading", { name: "Что создаём?" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^Новости/ }));
    expect(screen.getByRole("heading", { name: "Уведомления" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Моё" }));
    expect(screen.getByRole("heading", { name: "Гость 2048" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ошибка" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Не получилось загрузить");
  });

  it("does not create a user outside Telegram", async () => {
    window.history.replaceState({}, "", "/app");
    window.Telegram = undefined;
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 401 })));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Откройте приложение через Telegram" })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("requires age confirmation after the first exchange", async () => {
    window.history.replaceState({}, "", "/app");
    const firstProfile = { ...profile, age_confirmed: false };
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response("", { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ nonce: "nonce" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ profile: firstProfile, csrf_token: "csrf", created: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(profile), { status: 200 })));

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Мне исполнилось 14 лет" }));

    expect(await screen.findByLabelText("Карта событий")).toBeInTheDocument();
  });
});
