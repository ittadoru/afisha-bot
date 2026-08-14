import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const sourcePath = (name: string) => resolve(process.cwd(), "src", name);
const materialCss = readFileSync(sourcePath("material-system.css"), "utf8");
const layoutCss = readFileSync(sourcePath("styles.css"), "utf8");
const adminCss = readFileSync(sourcePath("admin.css"), "utf8");

describe("consumer material system", () => {
  it("owns all backdrop filters in one scoped stylesheet", () => {
    expect(layoutCss).not.toContain("backdrop-filter");
    expect(materialCss).toContain(":where(.mini-app, .site-shell, .public-event-page)");
    expect(materialCss).not.toContain(".admin-shell");
    expect(adminCss).not.toContain("--glass-");
  });

  it("keeps the requested hierarchy instead of one universal opacity", () => {
    expect(materialCss).toContain("rgb(var(--glass-milk-rgb) / .34)");
    expect(materialCss).toContain("rgb(var(--glass-card-rgb) / .48)");
    expect(materialCss).toContain("rgb(var(--glass-card-rgb) / .56)");
    expect(materialCss).toContain("rgb(var(--glass-card-rgb) / .64)");
    expect(materialCss).toContain("rgb(var(--glass-milk-rgb) / .68)");
  });

  it("keeps brand pigments stable without legacy smoke layers", () => {
    expect(materialCss).toContain("--glass-primary-optical-rgb: 66 100 42;");
    expect(materialCss).toContain("--glass-terra-optical-rgb: 175 82 43;");
    expect(materialCss).not.toContain("glass-smoke-green");
    expect(materialCss).not.toContain("glass-smoke-terra");
    expect(materialCss).not.toContain("rgb(54 88 68");
  });

  it("keeps inactive map chrome colourless and gives list city control the dock material", () => {
    expect(materialCss).toContain("rgb(var(--glass-milk-rgb) / .18)");
    expect(materialCss).toContain("rgb(var(--glass-milk-rgb) / .20)");
    expect(materialCss).toContain("blur(12px) saturate(100%)");
    expect(materialCss).not.toMatch(/\.map-glass-active \.floating-segment\s*\{[^}]*glass-pasture/s);
    expect(materialCss).not.toMatch(/\.maplibregl-ctrl-group\s*\{[^}]*glass-pasture/s);
    expect(materialCss).toContain("rgb(var(--glass-map-active-optical-rgb) / .80)");
    expect(materialCss).toContain('.mini-app:not(.map-glass-active):not([data-home-view="list"]) .dock-city-control');
    expect(materialCss).not.toMatch(/\[data-home-view="list"\] \.dock-city-control::before/);
    expect(materialCss).not.toMatch(/transition:[^}]*backdrop-filter/s);
  });

  it("does not stack a chrome material around the Company toolbar", () => {
    expect(materialCss).not.toContain(".people-toolbar");
    expect(materialCss).not.toContain("  .idea-status,");
    expect(layoutCss).toMatch(/\.people-toolbar\s*\{[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s);
    expect(layoutCss).toContain(".people-empty-state");
    expect(layoutCss).toContain(".people-card-open");
    expect(layoutCss).toMatch(/\.people-card-open\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;[^}]*width:\s*100%;[^}]*min-width:\s*0;/s);
    expect(layoutCss).toMatch(/\.people-card footer button\s*\{[^}]*min-height:\s*44px;/s);
  });

  it("keeps subpage rhythm single-guttered and full-width bars free of floating shadows", () => {
    expect(layoutCss).toContain("--subpage-gutter: 16px;");
    expect(layoutCss).toContain("--subpage-content-gap: 22px;");
    expect(layoutCss).toMatch(/\.mini-content\.subpage-mode > \.feed:not\([^}]+padding-inline:\s*var\(--subpage-gutter\)/s);
    expect(layoutCss).not.toMatch(/\.mini-content\.subpage-mode > \.feed:not\([^}]+width:[^}]+calc\(100% -/s);
    expect(materialCss).toMatch(/Full-width bars[^}]+box-shadow:\s*\n\s*inset 0 1px[^;]+\n\s*inset 0 -1px[^;]+;/s);
    expect(materialCss).toMatch(/\.profile-event \[data-ui="button"\]\s*\{[^}]*box-shadow:[^}]*inset 0 1px[^}]*inset 0 -1px/s);
  });

  it("lets material recipes own form and semantic surface backgrounds", () => {
    expect(materialCss).not.toContain(".profile-media-editor");
    expect(layoutCss).not.toMatch(/\.report-form select,[^{]+\{[^}]*background:/s);
    expect(layoutCss).not.toMatch(/\.notification\.urgent\s*\{[^}]*background:/s);
    expect(layoutCss).not.toMatch(/\.event-state\.success\s*\{[^}]*background:/s);
    expect(layoutCss).not.toMatch(/\.selected-city\.compact\s*\{[^}]*background:/s);
    expect(layoutCss).not.toMatch(/\.case-appeal-step\.available\s*\{[^}]*background:/s);
  });

  it("provides transparency, contrast, motion, and unsupported-browser fallbacks", () => {
    expect(materialCss).toContain("@supports not ((-webkit-backdrop-filter:");
    expect(materialCss).toContain("@media (prefers-reduced-transparency: reduce)");
    expect(materialCss).toContain("@media (prefers-contrast: more)");
    expect(materialCss).toContain("@media (prefers-reduced-motion: reduce)");
    expect(materialCss).not.toContain('[data-material]:not([data-material="none"])');
    expect(materialCss).toContain('[data-ui="button"][data-variant="destructive"]');
    expect(materialCss).toContain('[data-material="overlay"]');
    expect(materialCss.match(/\.chat-message\.organizer/g)?.length).toBeGreaterThanOrEqual(3);
  });

  it("keeps portal scrims cheap and freezes map filters behind open dialogs", () => {
    expect(materialCss).toMatch(/\.sheet-overlay, \.alert-dialog-overlay\)[^{]*\{[^}]*backdrop-filter: none/s);
    expect(materialCss).toContain(":has(");
    expect(materialCss).toContain('[data-state="open"]');
  });

  it("does not regress read-notification content opacity or the old performance selector", () => {
    expect(layoutCss).not.toContain(".notification-item");
    expect(layoutCss).not.toMatch(/\.notification\.read\s*\{[^}]*opacity/s);
    expect(materialCss).not.toMatch(/\.notification\.read\s*\{[^}]*opacity/s);
  });
});
