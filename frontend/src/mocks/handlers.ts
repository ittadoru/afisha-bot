import { faker } from "@faker-js/faker";
import { http, HttpResponse } from "msw";

faker.seed(20260801);

export const handlers = [
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
