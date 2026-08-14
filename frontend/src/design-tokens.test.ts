import { readFileSync, readdirSync } from "node:fs";
import { basename, extname, join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const sourceRoot = resolve(process.cwd(), "src");
const tokenPath = join(sourceRoot, "design-tokens.css");
const tokenCss = readFileSync(tokenPath, "utf8");

const canonicalChannels = {
  caspian: "23 107 135",
  sand: "232 215 181",
  pasture: "96 124 74",
  terracotta: "185 104 69",
  milk: "247 243 234",
} as const;

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return [path];
  });
}

function isConsumerSource(path: string): boolean {
  const extension = extname(path);
  const name = basename(path);
  if (![".css", ".ts", ".tsx"].includes(extension)) return false;
  if (name.includes(".test.") || name.includes(".spec.")) return false;
  return name !== "admin.css" && name !== "admin-app.tsx";
}

describe("canonical consumer design tokens", () => {
  it("locks the five documented palette primitives and alpha-ready aliases", () => {
    for (const [name, channels] of Object.entries(canonicalChannels)) {
      expect(tokenCss).toContain(`--brand-${name}-rgb: ${channels};`);
      expect(tokenCss).toContain(`--${name}: rgb(var(--brand-${name}-rgb));`);
    }
    expect(tokenCss).toContain("--brand-shadow-rgb: 55 49 36;");
  });

  it("loads canonical tokens before layout and material styles", () => {
    const entrypoint = readFileSync(join(sourceRoot, "main.tsx"), "utf8");
    const tokensAt = entrypoint.indexOf('import "@/design-tokens.css"');
    const layoutAt = entrypoint.indexOf('import "@/styles.css"');
    const materialAt = entrypoint.indexOf('import "@/material-system.css"');

    expect(tokensAt).toBeGreaterThan(-1);
    expect(tokensAt).toBeLessThan(layoutAt);
    expect(layoutAt).toBeLessThan(materialAt);
  });

  it("rejects known legacy brand approximations without restricting category or status colors", () => {
    const forbiddenPigments = [
      new RegExp("#" + "08786c\\b", "i"),
      /#(?:365744|294737|405535)\b/i,
      /rgb\(54\s+88\s+68(?:\s*\/|\))/i,
      /rgb\(91\s+125\s+72(?:\s*\/|\))/i,
      /rgb\(13\s+38\s+29(?:\s*\/|\))/i,
    ];
    const offenders = sourceFiles(sourceRoot)
      .filter(isConsumerSource)
      .filter((path) => {
        const source = readFileSync(path, "utf8");
        return forbiddenPigments.some((pattern) => pattern.test(source));
      })
      .map((path) => relative(sourceRoot, path));

    expect(offenders).toEqual([]);
  });
});
