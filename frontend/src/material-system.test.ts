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

  it("provides transparency, contrast, motion, and unsupported-browser fallbacks", () => {
    expect(materialCss).toContain("@supports not ((-webkit-backdrop-filter:");
    expect(materialCss).toContain("@media (prefers-reduced-transparency: reduce)");
    expect(materialCss).toContain("@media (prefers-contrast: more)");
    expect(materialCss).toContain("@media (prefers-reduced-motion: reduce)");
    expect(materialCss).not.toContain('[data-material]:not([data-material="none"])');
    expect(materialCss).toContain('[data-ui="button"][data-variant="destructive"]');
    expect(materialCss).toContain('[data-material="overlay"]');
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
