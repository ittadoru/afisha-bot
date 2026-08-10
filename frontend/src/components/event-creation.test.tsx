import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EventCreation } from "./event-creation";

vi.mock("@/components/event-map", () => ({
  EventMap: ({ onLocationChange }: { onLocationChange?: (location: object) => void }) => (
    <button
      type="button"
      onClick={() => onLocationChange?.({
        latitude: 42.98,
        longitude: 47.5,
        display_name: "Проспект Имама Шамиля, Махачкала",
        street: "Проспект Имама Шамиля",
        house_number: null,
        precision: "street",
      })}
    >
      Установить тестовую точку
    </button>
  ),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-08-10T01:00:00Z"));
});

describe("EventCreation", () => {
  it("keeps address continuation disabled until the organizer confirms it", () => {
    render(
      <EventCreation
        city={{ id: "city-1", name: "Махачкала", center_latitude: 42.98, center_longitude: 47.5 }}
        categories={[{ id: "walks", name: "Прогулки", is_special: false, organizer_selectable: true }]}
        csrfToken="csrf"
        organizerStatus="trusted"
        onDirtyChange={vi.fn()}
        registerDiscard={vi.fn()}
        onChooseCity={vi.fn()}
        onFinished={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/^Название/), { target: { value: "Прогулка у моря" } });
    fireEvent.change(screen.getByLabelText(/^Категория/), { target: { value: "walks" } });
    fireEvent.change(screen.getByLabelText(/^Описание/), { target: { value: "Неспешная прогулка и знакомство." } });
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    fireEvent.change(screen.getByLabelText("Начало"), { target: { value: "2026-08-12T12:00" } });
    fireEvent.change(screen.getByLabelText("Окончание"), { target: { value: "2026-08-12T14:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    fireEvent.click(screen.getByRole("button", { name: "Установить тестовую точку" }));
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    const continueButton = screen.getByRole("button", { name: "Продолжить" });
    expect(continueButton).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Улица/), { target: { value: "Проспект Имама Шамиля" } });
    fireEvent.change(screen.getByLabelText(/Дом, место или ориентир/), { target: { value: "Главный вход" } });
    expect(continueButton).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /Я подтверждаю/ }));
    expect(continueButton).toBeEnabled();
  });
});
