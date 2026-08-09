import { faker } from "@faker-js/faker";
import { http, HttpResponse } from "msw";

faker.seed(20260801);

const mockProfile = {
  public_id: "12061921",
  display_name: "Амина",
  bio: "Люблю горные маршруты, камерные встречи и море в несезон.",
  selected_city_id: "makhachkala",
  age_confirmed: true,
  organizer_status: "trusted",
  upcoming_count: 4,
  completed_count: 12,
  successful_events: 9,
  version: 3,
  avatar_url: null,
};

const mockEvents = [
  {
    id: "11111111-1111-4111-8111-111111111111", kind: "regular", lifecycle_status: "published", category: "Прогулки", category_slug: "walks", title: "Закатная прогулка у моря", description: "Спокойная прогулка вдоль побережья и знакомство за чаем.", starts_at: "2026-08-12T16:30:00+03:00", ends_at: "2026-08-12T19:00:00+03:00", visible_address: "Родопский бульвар", participant_count: 8, capacity: 14, available_places: 6, interest_count: 16, viewer_membership: "none", viewer_is_organizer: false, photo_url: "/brand/dagestan-profile-hero.jpg", organizer_public_id: "12061921", organizer_name: "Амина", organizer_status: "trusted", latitude: 42.976, longitude: 47.502, chat_enabled: true,
  },
  {
    id: "22222222-2222-4222-8222-222222222222", kind: "regular", lifecycle_status: "published", category: "Туризм", category_slug: "tourism", title: "Выходные в Гунибском районе", description: "Неспешный маршрут, горный воздух и панорамы старых аулов.", starts_at: "2026-08-15T07:00:00+03:00", ends_at: "2026-08-16T18:00:00+03:00", visible_address: "Общая улица, точка после вступления", participant_count: 11, capacity: 18, available_places: 7, interest_count: 23, viewer_membership: "none", viewer_is_organizer: false, photo_url: "/brand/dagestan-profile-hero.jpg", organizer_public_id: "12061921", organizer_name: "Амина", organizer_status: "trusted", latitude: 42.991, longitude: 47.486, chat_enabled: true,
  },
  {
    id: "33333333-3333-4333-8333-333333333333", kind: "regular", lifecycle_status: "published", category: "Творчество", category_slug: "creativity", title: "Вечер керамики и разговоров", description: "Пробуем ручную лепку и знакомимся в небольшой мастерской.", starts_at: "2026-08-18T18:00:00+03:00", ends_at: "2026-08-18T21:00:00+03:00", visible_address: "Улица Дахадаева", participant_count: 6, capacity: 10, available_places: 4, interest_count: 14, viewer_membership: "none", viewer_is_organizer: false, photo_url: "/brand/dagestan-profile-hero.jpg", organizer_public_id: "12061921", organizer_name: "Амина", organizer_status: "trusted", latitude: 42.969, longitude: 47.513, chat_enabled: true,
  },
];

export const handlers = [
  http.get("*/account/me", () => HttpResponse.json(mockProfile, { headers: { "X-Afisha-CSRF": "mock-csrf" } })),
  http.get("*/geo/catalog", () => HttpResponse.json({ cities: [{ id: "makhachkala", name: "Махачкала", center_latitude: 42.9831, center_longitude: 47.5047, service_radius_m: 20000 }], categories: [{ id: "walks", slug: "walks", name: "Прогулки", is_special: false, organizer_selectable: true }, { id: "tourism", slug: "tourism", name: "Туризм", is_special: false, organizer_selectable: true }, { id: "creativity", slug: "creativity", name: "Творчество", is_special: false, organizer_selectable: true }] })),
  http.get("*/events", ({ request }) => {
    const view = new URL(request.url).searchParams.get("view");
    if (view === "map") return HttpResponse.json({ items: [
      { marker_type: "event", id: mockEvents[0].id, kind: "regular", category_slug: "walks", category: "Прогулки", title: mockEvents[0].title, latitude: 42.976, longitude: 47.502, street_name: null, event_count: null, event_ids: null },
      { marker_type: "event", id: mockEvents[2].id, kind: "regular", category_slug: "creativity", category: "Творчество", title: mockEvents[2].title, latitude: 42.969, longitude: 47.513, street_name: null, event_count: null, event_ids: null },
      { marker_type: "street", id: null, kind: "regular", category_slug: null, category: null, title: null, latitude: 42.991, longitude: 47.486, street_name: "улица Батырая", event_count: 2, event_ids: [mockEvents[1].id, mockEvents[2].id] },
    ] });
    return HttpResponse.json({ items: mockEvents });
  }),
  http.get("*/events/:eventId", ({ params }) => HttpResponse.json(mockEvents.find((event) => event.id === params.eventId) ?? mockEvents[0])),
  http.get("*/looking-posts", () => HttpResponse.json({ items: [
    { id: "44444444-4444-4444-8444-444444444444", title: "Кто на утреннюю прогулку?", body: "Хочу пройтись по набережной до жары и после выпить кофе.", category: "Прогулки", created_at: "2026-08-10T08:20:00+03:00", like_count: 7, question_count: 2, viewer_liked: false, is_author: false, status: "active", remaining_seconds: 162000, author: { display_name: "Мурад", avatar_url: null } },
    { id: "55555555-5555-4555-8555-555555555555", title: "Собираю небольшую группу в Гуниб", body: "Без гонки и сложных подъёмов. Важнее виды, разговоры и хороший чай.", category: "Туризм", created_at: "2026-08-09T18:10:00+03:00", like_count: 12, question_count: 4, viewer_liked: true, is_author: false, status: "active", remaining_seconds: 111000, author: { display_name: "Патимат", avatar_url: null } },
  ], next_cursor: null })),
  http.get("*/account/notifications", () => HttpResponse.json([
    { id: "notice-1", title: "Встреча уже завтра", body: "Организатор прогулки уточнил время сбора.", importance: "normal", read_at: null },
    { id: "notice-2", title: "Нужно подтвердить участие", body: "Ответьте до 18:00, чтобы место не перешло следующему участнику.", importance: "critical", read_at: null },
  ])),
  http.get("*/geo/reverse", () =>
    HttpResponse.json({
      display_name: `${faker.location.street()}, Махачкала, Республика Дагестан`,
      street: faker.location.street(),
      city: "Махачкала",
      region: "Республика Дагестан",
      provider_place_id: "mock-place",
      locale: "ru",
      precision: "street",
    }),
  ),
];
