import { fireEvent, render, screen } from "@testing-library/react";
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
    expect(screen.getByRole("navigation", { name: "Основные разделы" })).toBeInTheDocument();
  });

  it("allows visiting every future Mini App section", async () => {
    window.history.replaceState({}, "", "/app");
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Ищу людей" }));
    expect(screen.getByRole("heading", { name: "Найдите компанию" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Создать" }));
    expect(screen.getByRole("heading", { name: "Что создаём?" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Новости" }));
    expect(screen.getByRole("heading", { name: "Уведомления" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Моё" }));
    expect(screen.getByRole("heading", { name: "Амина" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ошибка" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Не получилось загрузить");
  });
});
