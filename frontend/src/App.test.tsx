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

function okJson(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Afisha-CSRF": "csrf-token" },
  });
}

beforeEach(() => {
  window.Telegram = {
    WebApp: {
      initData: "signed-init-data",
      ready: vi.fn(),
      expand: vi.fn(),
    },
  };
  vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/geo/catalog")) return okJson({ cities: [], categories: [] });
    if (url.endsWith("/account/notifications")) return okJson([]);
    return okJson(profile);
  }));
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
    expect(screen.getByRole("group", { name: "Разделы главного экрана" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Основные разделы" })).not.toBeInTheDocument();
  });

  it("allows visiting every future Mini App section", async () => {
    window.history.replaceState({}, "", "/app");
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Ищу людей" }));
    expect(await screen.findByRole("heading", { name: "Найдите компанию" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Создать объявление" }));
    expect(await screen.findByRole("heading", { name: "Новая идея" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Вернуться на главный экран" }));
    fireEvent.click(await screen.findByRole("button", { name: "Открыть уведомления" }));
    expect(await screen.findByRole("heading", { name: "Уведомления" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Вернуться на главный экран" }));
    fireEvent.click(await screen.findByRole("button", { name: "Открыть профиль" }));
    expect(await screen.findByRole("heading", { name: "Гость 2048" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ошибка" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не получилось загрузить");
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
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/account/me")) return new Response("", { status: 401 });
      if (url.endsWith("/auth/mini/bootstrap")) return okJson({ nonce: "nonce" });
      if (url.endsWith("/auth/mini/exchange")) return okJson({ profile: firstProfile, csrf_token: "csrf", created: true });
      if (url.endsWith("/account/age-consent")) return okJson(profile);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [], categories: [] });
      if (url.endsWith("/account/notifications")) return okJson([]);
      return okJson(profile);
    }));

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Мне исполнилось 14 лет" }));

    expect(await screen.findByLabelText("Карта событий")).toBeInTheDocument();
  });
});
