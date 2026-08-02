import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("landing is usable and has no automatically detectable accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Есть куда пойти/i })).toBeVisible();
  await expect(page.getByRole("button", { name: "Ехала →" })).toHaveCSS("min-height", "48px");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("main action opens the map workspace", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Ехала →" }).click();
  await expect(page.getByLabel("Карта событий")).toBeVisible();
  await expect(page.getByText("Точное место")).toBeVisible();
  await expect(page.getByText("Общая улица")).toBeVisible();
});
