import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("@/components/event-map", () => ({
  EventMap: () => <section aria-label="Карта событий" />,
}));

afterEach(cleanup);

const city = { id: "10000000-0000-4000-8000-000000000001", name: "Махачкала", latitude: 42.9849, longitude: 47.5047 };

const profile = {
  public_id: "12345678",
  display_name: "Гость 2048",
  bio: null,
  selected_city_id: city.id,
  age_confirmed: true,
  background_url: null,
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
    if (url.endsWith("/geo/catalog")) return okJson({ cities: [city], categories: [] });
    if (url.endsWith("/account/notifications")) return okJson([]);
    if (url.includes("/events?")) return okJson({ items: [] });
    if (url.includes("/looking-posts?")) return okJson({ items: [], next_cursor: null });
    return okJson(profile);
  }));
});

describe("landing", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
  });

  it("shows the accepted headline and main action", () => {
    render(<App />);
    expect(screen.getByRole("main")).toHaveClass("site-shell");
    expect(screen.getByRole("main")).toHaveAttribute("data-canvas", "public");
    expect(screen.getByRole("heading", { name: /Есть куда пойти/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ехала →" })).toHaveAttribute("href", "/app");
    expect(screen.getByRole("link", { name: "Открыть карту" })).toHaveAttribute("href", "/app");
  });

  it("shows the universal loader while Mini App authentication is pending", async () => {
    window.history.replaceState({}, "", "/app");
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent("Ургъула…");
  });

  it("opens the map directly at /app", async () => {
    window.history.replaceState({}, "", "/app");

    render(<App />);

    expect(await screen.findByLabelText("Карта событий")).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).endsWith("/account/profile/city"))).toBe(false);
    expect(screen.getByRole("group", { name: "Разделы главного экрана" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Основные разделы" })).not.toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveClass("map-glass-active");
    expect(screen.getByRole("main")).toHaveAttribute("data-canvas", "discovery");
    expect(screen.getByRole("main")).toHaveAttribute("data-home-view", "map");

    fireEvent.click(screen.getByRole("button", { name: "Список" }));
    await waitFor(() => expect(screen.getByRole("main")).not.toHaveClass("map-glass-active"));
    expect(screen.getByRole("main")).not.toHaveClass("list-material-active");
    expect(screen.getByRole("main")).toHaveAttribute("data-home-view", "list");
    expect(screen.getByRole("group", { name: "Вид событий" })).toHaveAttribute("data-material", "chrome");

    fireEvent.click(screen.getByRole("button", { name: "Карта" }));
    await waitFor(() => {
      expect(screen.getByRole("main")).toHaveClass("map-glass-active");
      expect(screen.getByRole("main")).toHaveAttribute("data-home-view", "map");
    });

    fireEvent.click(screen.getByRole("button", { name: "Компания" }));
    await waitFor(() => {
      expect(screen.getByRole("main")).not.toHaveClass("map-glass-active");
      expect(screen.getByRole("main")).not.toHaveClass("list-material-active");
      expect(screen.getByRole("main")).toHaveAttribute("data-canvas", "discovery");
      expect(screen.getByRole("main")).toHaveAttribute("data-home-view", "company");
    });
  });

  it("requires a city for a profile without a saved selection and saves the first city", async () => {
    window.history.replaceState({}, "", "/app");
    const profileWithoutCity = { ...profile, selected_city_id: null };
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/account/me")) return okJson(profileWithoutCity);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [city], categories: [] });
      if (url.endsWith("/account/onboarding") && init?.method === "POST") return okJson(profile);
      return okJson(profileWithoutCity);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText(/Выберите город и подтвердите возраст/)).toBeInTheDocument();
    expect(screen.queryByText("Назад")).not.toBeInTheDocument();
    expect(await screen.findByRole("radio", { name: city.name })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ехала →" })).toBeDisabled();
  });

  it("keeps mandatory city selection open when saving fails", async () => {
    window.history.replaceState({}, "", "/app");
    const profileWithoutCity = { ...profile, selected_city_id: null };
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/account/me")) return okJson(profileWithoutCity);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [city], categories: [] });
      if (url.endsWith("/account/onboarding")) return okJson({}, 500);
      return okJson(profileWithoutCity);
    }));

    render(<App />);
    fireEvent.click(await screen.findByRole("radio", { name: city.name }));
    fireEvent.click(screen.getByRole("button", { name: "Ехала →" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось сохранить выбор");
    expect(screen.getByText("Ваш город")).toBeInTheDocument();
    expect(screen.queryByLabelText("Карта событий")).not.toBeInTheDocument();
  });

  it("allows visiting every future Mini App section", async () => {
    window.history.replaceState({}, "", "/app");
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Компания" }));
    expect(await screen.findByRole("heading", { name: "Найдите компанию" })).toBeInTheDocument();
    const emptyHeading = await screen.findByRole("heading", { name: "В этом городе пока нет идей" });
    expect(emptyHeading.closest(".people-screen")).toHaveClass("people-screen--empty");
    expect(emptyHeading.closest(".people-empty-state")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Создать идею" })).toHaveAttribute("data-variant", "default");

    fireEvent.click(screen.getByRole("button", { name: "Создать объявление" }));
    expect(await screen.findByRole("heading", { name: "Новая идея" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Вернуться на главный экран" })).toHaveLength(1);
    expect(screen.queryByText("← Назад")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Вернуться на главный экран" }));
    fireEvent.click(await screen.findByRole("button", { name: "Открыть уведомления" }));
    expect(await screen.findByRole("heading", { name: "Уведомления" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Вернуться на главный экран" }));
    fireEvent.click(await screen.findByRole("button", { name: "Открыть профиль" }));
    expect(await screen.findByRole("heading", { name: "Гость 2048" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Стандартный фон профиля" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Пожаловаться на профиль" })).not.toBeInTheDocument();
    expect(screen.queryByText("Выйти из аккаунта")).not.toBeInTheDocument();
    expect(screen.queryByText("Добавить")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Редактировать профиль" }));
    expect(screen.getAllByText("Добавить")).toHaveLength(2);
    expect(screen.getByText("Фон профиля")).toBeInTheDocument();
    expect(screen.getByText("Фотография")).toBeInTheDocument();
    expect(screen.queryByText("Открыть профиль")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Восьмизначный номер")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Вернуться на главный экран" }));
    fireEvent.click(screen.getByRole("button", { name: "Ошибка" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не получилось загрузить");
  });

  it("ignores an aborted stale looking-post response after sorting changes", async () => {
    window.history.replaceState({}, "", "/app");
    let resolveFirst: ((response: Response) => void) | null = null;
    let lookingCalls = 0;
    const signals: AbortSignal[] = [];
    vi.stubGlobal("fetch", vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/geo/catalog")) return Promise.resolve(okJson({ cities: [city], categories: [] }));
      if (url.endsWith("/account/notifications")) return Promise.resolve(okJson([]));
      if (url.includes("/looking-posts?")) {
        lookingCalls += 1;
        if (lookingCalls === 1) {
          if (init?.signal) signals.push(init.signal);
          return new Promise<Response>((resolve) => { resolveFirst = resolve; });
        }
        return Promise.resolve(okJson({ items: [{ id: "new", title: "Свежая идея", body: "Описание", category: "Прогулки", created_at: "2026-08-11T12:00:00+03:00", like_count: 0, question_count: 0, viewer_liked: false, is_author: false, status: "active", remaining_seconds: 100, author: { public_id: "12345678", display_name: "Анна", avatar_url: null, avatar_thumbnail_url: null } }], next_cursor: null }));
      }
      return Promise.resolve(okJson(profile));
    }));

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Компания" }));
    const companyHeading = await screen.findByRole("heading", { name: "Найдите компанию" });
    expect(companyHeading.closest(".people-screen")).toHaveClass("people-screen--loading");
    expect(companyHeading.closest(".people-screen")?.querySelector(".people-list-scroll")).toHaveClass("people-list-scroll--state", "people-list-scroll--loading");
    fireEvent.click(await screen.findByRole("button", { name: "Старые" }));
    const freshHeading = await screen.findByRole("heading", { name: "Свежая идея" });
    expect(freshHeading.closest(".people-screen")).toHaveClass("people-screen--ready");
    const card = freshHeading.closest("article");
    expect(card).not.toBeNull();
    expect(card).not.toHaveAttribute("role");
    expect(card).not.toHaveAttribute("tabindex");
    const openAction = within(card!).getByRole("link", { name: "Открыть идею «Свежая идея». Автор Анна" });
    const likeAction = within(card!).getByRole("button", { name: "Отметить нравится. Всего 0" });
    expect(openAction).toHaveClass("people-card-open");
    expect(openAction).toHaveAttribute("href", "/app/company/new");
    expect(openAction.contains(likeAction)).toBe(false);
    expect(signals[0]?.aborted).toBe(true);

    act(() => resolveFirst?.(okJson({ items: [{ id: "old", title: "Устаревшая идея" }], next_cursor: null })));
    await waitFor(() => expect(screen.queryByText("Устаревшая идея")).not.toBeInTheDocument());
  });

  it("retries a failed looking-post request only after the user asks", async () => {
    window.history.replaceState({}, "", "/app");
    let lookingCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [city], categories: [] });
      if (url.endsWith("/account/notifications")) return okJson([]);
      if (url.includes("/looking-posts?")) {
        lookingCalls += 1;
        return lookingCalls === 1
          ? okJson({}, 503)
          : okJson({ items: [], next_cursor: null });
      }
      return okJson(profile);
    }));

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Компания" }));
    const errorMessage = await screen.findByText("Не удалось загрузить идеи");
    expect(errorMessage.closest(".people-screen")).toHaveClass("people-screen--error");
    expect(errorMessage.closest(".people-screen")?.querySelector(".people-list-scroll")).toHaveClass("people-list-scroll--state", "people-list-scroll--error");
    expect(lookingCalls).toBe(1);

    const retry = screen.getByRole("button", { name: "Повторить" });
    expect(retry).toHaveAttribute("data-variant", "outline");
    fireEvent.click(retry);
    const emptyHeading = await screen.findByRole("heading", { name: "В этом городе пока нет идей" });
    expect(emptyHeading.closest(".people-screen")).toHaveClass("people-screen--empty");
    expect(emptyHeading.closest(".people-screen")?.querySelector(".people-list-scroll")).toHaveClass("people-list-scroll--state", "people-list-scroll--empty");
    expect(emptyHeading.closest(".people-empty-state")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Создать идею" })).toHaveAttribute("data-variant", "default");
    expect(lookingCalls).toBe(2);
  });

  it("shows looking-post questions without a share action", async () => {
    const postId = "11111111-1111-4111-8111-111111111111";
    window.history.replaceState({}, "", `/app/looking/${postId}`);
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/account/me")) return okJson(profile);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [], categories: [] });
      if (url.endsWith("/account/notifications")) return okJson([]);
      if (url.endsWith(`/looking-posts/${postId}/questions`)) return okJson({ items: [{ id: "q1", question: "Можно без опыта?", answer: "Да, конечно", asker: { public_id: "87654321", display_name: "Мурад", avatar_thumbnail_url: "/api/profiles/87654321/avatar?size=64" } }], pending: [{ id: "q2", question: "Где встречаемся?" }], viewer_can_ask: false, ask_block_reason: "unanswered_question_exists" });
      if (url.endsWith(`/looking-posts/${postId}`)) return okJson({ id: postId, title: "Прогулка утром", body: "Ищем компанию", category: "Прогулки", created_at: "2026-08-10T09:00:00+03:00", like_count: 2, question_count: 1, viewer_liked: false, is_author: false, status: "active", remaining_seconds: 3600, author: { public_id: "12345678", display_name: "Амина", avatar_url: null } });
      return okJson(profile);
    }));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Прогулка утром" })).toBeInTheDocument();
    expect(screen.getByText("Можно без опыта?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Открыть профиль Мурад" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Пожаловаться" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Пожаловаться на ответ" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Задайте вопрос автору")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отправить вопрос" })).toBeDisabled();
    expect(screen.getByText("Сначала дождитесь ответа на предыдущий вопрос.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Поделиться/ })).not.toBeInTheDocument();
  });

  it("keeps a single share action on event detail", async () => {
    const eventId = "22222222-2222-4222-8222-222222222222";
    window.history.replaceState({}, "", `/app/event/${eventId}`);
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/account/me")) return okJson(profile);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [], categories: [] });
      if (url.endsWith("/account/notifications")) return okJson([]);
      if (url.endsWith(`/events/${eventId}`)) return okJson({ id: eventId, kind: "regular", lifecycle_status: "published", category: "Прогулки", category_slug: "walks", title: "Прогулка у моря", description: "Спокойная встреча", starts_at: "2026-08-12T16:00:00+03:00", ends_at: "2026-08-12T18:00:00+03:00", visible_address: "Набережная", participant_count: 4, capacity: 10, available_places: 6, interest_count: 3, viewer_interested: false, viewer_is_organizer: false, viewer_membership: "participating", photo_url: "/brand/dagestan-profile-hero.jpg", organizer_public_id: "87654321", organizer_name: "Амина", organizer_status: "trusted", chat_enabled: true });
      if (url.includes("/profiles/87654321/events")) return okJson({ items: [], next_offset: null });
      if (url.endsWith("/profiles/87654321")) return okJson({ ...profile, public_id: "87654321", display_name: "Амина" });
      return okJson(profile);
    }));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Прогулка у моря" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Поделиться событием" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Пожаловаться на событие" }).closest("footer")).toHaveClass("event-sticky-cta");
    expect(screen.queryByRole("button", { name: /^Поделиться$/ })).not.toBeInTheDocument();
    const chat = screen.getByRole("button", { name: "Открыть чат события" });
    expect(chat.querySelector("i")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Организатор.*Амина/ }));
    expect(await screen.findByText("Публичный профиль")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Амина" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Пожаловаться на профиль" })).toBeInTheDocument();
    expect(screen.queryByText("Пожаловаться на профиль")).not.toBeInTheDocument();
  });

  it("uses a compact two-step event report wizard", async () => {
    const eventId = "22222222-2222-4222-8222-222222222222";
    window.history.replaceState({}, "", `/app/report/event/${eventId}`);

    render(<App />);

    expect(await screen.findByRole("heading", { name: "На что жалоба?" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.queryByText("Дата и время")).not.toBeInTheDocument();
    expect(screen.queryByText("Место")).not.toBeInTheDocument();
    expect(screen.queryByText("Событие целиком")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Фотография/ }));
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    expect(screen.getByLabelText("Причина")).toHaveValue("inappropriate_content");
    expect(screen.getByText("Что произошло?")).toBeInTheDocument();
  });

  it("stretches the organizer management action across the sticky footer", async () => {
    const eventId = "33333333-3333-4333-8333-333333333333";
    window.history.replaceState({}, "", `/app/event/${eventId}`);
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith(`/events/${eventId}`)) return okJson({ id: eventId, kind: "regular", lifecycle_status: "published", category: "Творчество", category_slug: "creativity", title: "Мастерская", description: "Встреча", starts_at: "2026-08-18T18:00:00+03:00", ends_at: "2026-08-18T21:00:00+03:00", visible_address: "Дахадаева", participant_count: 2, capacity: 10, available_places: 8, interest_count: 1, viewer_interested: false, viewer_is_organizer: true, viewer_membership: "participating", photo_url: "/brand/dagestan-profile-hero.jpg", organizer_public_id: profile.public_id, organizer_name: profile.display_name, organizer_status: "trusted", chat_enabled: true });
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [], categories: [] });
      if (url.endsWith("/account/notifications")) return okJson([]);
      return okJson(profile);
    }));

    render(<App />);

    const manage = await screen.findByRole("button", { name: "Управлять событием" });
    expect(manage.closest("footer")).toHaveClass("event-sticky-cta", "solo");
    expect(screen.queryByRole("button", { name: "Пожаловаться на событие" })).not.toBeInTheDocument();
  });

  it("opens a chat author profile and returns to the chat", async () => {
    const eventId = "22222222-2222-4222-8222-222222222222";
    window.history.replaceState({}, "", `/app/event/${eventId}/chat`);
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/account/me")) return okJson(profile);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [], categories: [] });
      if (url.endsWith("/account/notifications")) return okJson([]);
      if (url.endsWith(`/events/${eventId}/chat`)) return okJson({ items: [
        { id: "m1", body: "Встречаемся у входа", created_at: "2026-08-10T12:00:00+03:00", author_display_name: "Мурад", author_public_id: "87654321", author_avatar_thumbnail_url: "/api/profiles/87654321/avatar?size=64", author_is_organizer: false, author_is_viewer: false },
        { id: "m2", body: "Буду вовремя", created_at: "2026-08-10T12:01:00+03:00", author_display_name: "Мурад", author_public_id: "87654321", author_avatar_thumbnail_url: "/api/profiles/87654321/avatar?size=64", author_is_organizer: false, author_is_viewer: false },
      ] });
      if (url.endsWith(`/events/${eventId}`)) return okJson({ title: "Прогулка", chat_enabled: true, viewer_is_organizer: false });
      if (url.includes("/profiles/87654321/events")) return okJson({ items: [], next_offset: null });
      if (url.endsWith("/profiles/87654321")) return okJson({ ...profile, public_id: "87654321", display_name: "Мурад" });
      return okJson(profile);
    }));

    render(<App />);
    expect(await screen.findAllByRole("button", { name: "Открыть профиль Мурад" })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Открыть профиль Мурад" }));
    expect(await screen.findByRole("heading", { name: "Мурад" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Вернуться на главный экран" }));
    expect(await screen.findByText("Встречаемся у входа")).toBeInTheDocument();
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
      if (url.endsWith("/account/onboarding")) return okJson(profile);
      if (url.endsWith("/geo/catalog")) return okJson({ cities: [city], categories: [] });
      return okJson(profile);
    }));

    render(<App />);
    fireEvent.click(await screen.findByRole("radio", { name: city.name }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Мне исполнилось 14 лет/i }));
    fireEvent.click(screen.getByRole("button", { name: "Ехала →" }));

    expect(await screen.findByLabelText("Карта событий")).toBeInTheDocument();
  });
});
