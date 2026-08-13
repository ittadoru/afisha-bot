import { describe, expect, it } from "vitest";
import { mapCategoryIconMarkup } from "./map-category-icon";

describe("mapCategoryIconMarkup", () => {
  it("renders the allowlisted catalog icon as accessible static SVG", () => {
    const markup = mapCategoryIconMarkup("graduation-cap", "education");

    expect(markup).toContain("<svg");
    expect(markup).toContain('aria-hidden="true"');
    expect(markup).toContain("lucide-graduation-cap");
  });

  it("keeps legacy category slugs visible during the compatible rollout", () => {
    expect(mapCategoryIconMarkup(null, "walks")).toContain("lucide-mountain");
    expect(mapCategoryIconMarkup(null, "work")).toContain("lucide-graduation-cap");
  });

  it("uses Shapes for an unknown server value", () => {
    expect(mapCategoryIconMarkup("not-allowlisted", "unknown")).toContain(
      "lucide-shapes",
    );
  });
});
