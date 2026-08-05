import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("landing is usable and has no automatically detectable accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Есть куда пойти/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ехала →" })).toHaveCSS("min-height", "48px");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("main action navigates to the directly reloadable Mini App route", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Ехала →" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByLabel("Карта событий")).toBeVisible();
  await expect(page.getByText("Точное место")).toBeVisible();
  await expect(page.getByText("Общая улица")).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("Карта событий")).toBeVisible();
});

test("direct /app opening shows the current map demo", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByLabel("Карта событий")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Основные разделы" })).toBeVisible();
  await page.getByRole("button", { name: "Показать список" }).click();
  await expect(page.getByLabel("Список событий")).toBeVisible();
  await page.getByRole("button", { name: "Ищу людей" }).click();
  await expect(page.getByRole("heading", { name: "Найдите компанию" })).toBeVisible();
  await page.getByRole("button", { name: "Новости" }).click();
  await expect(page.getByRole("heading", { name: "Уведомления" })).toBeVisible();
});
