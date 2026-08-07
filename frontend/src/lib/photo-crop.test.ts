import { describe, expect, it } from "vitest";

import { cropFractions } from "./photo-crop";

describe("cropFractions", () => {
  it("maps the full 4:3 frame of a landscape 4:3 photo", () => {
    const container = { width: 375, height: 667 };
    const canvas = { left: 0, top: 0, width: 375, height: 281.25 };
    const box = { x: 0, y: 0, width: 100, height: 42.17 };

    const crop = cropFractions(box, container, canvas);

    expect(crop.x).toBeCloseTo(0);
    expect(crop.y).toBeCloseTo(0);
    expect(crop.width).toBeCloseTo(1);
    expect(crop.height).toBeCloseTo(1);
    expect((crop.width * 4000) / (crop.height * 3000)).toBeCloseTo(4 / 3, 2);
  });

  it("maps a 4:3 frame cropped from a square source", () => {
    const container = { width: 375, height: 375 };
    const canvas = { left: 0, top: 0, width: 375, height: 375 };
    const box = { x: 0, y: 12.5, width: 100, height: 75 };

    const crop = cropFractions(box, container, canvas);

    expect(crop.x).toBeCloseTo(0);
    expect(crop.y).toBeCloseTo(0.125);
    expect(crop.width).toBeCloseTo(1);
    expect(crop.height).toBeCloseTo(0.75);
    expect((crop.width * 1200) / (crop.height * 1200)).toBeCloseTo(4 / 3, 2);
  });

  it("maps a 4:3 frame from a portrait 3:4 photo to a horizontal box", () => {
    const container = { width: 375, height: 667 };
    const canvas = { left: 46.875, top: 0, width: 281.25, height: 375 };
    const box = { x: 12.5, y: 12.3, width: 75, height: 31.63 };

    const crop = cropFractions(box, container, canvas);

    expect(crop.x).toBeCloseTo(0);
    expect(crop.y).toBeCloseTo(82.04 / 375, 2);
    expect(crop.width).toBeCloseTo(1);
    expect(crop.height).toBeCloseTo(0.5626, 2);
    expect(crop.x + crop.width).toBeLessThanOrEqual(1.000001);
    expect(crop.y + crop.height).toBeLessThanOrEqual(1.000001);
    expect((crop.width * 3000) / (crop.height * 4000)).toBeCloseTo(4 / 3, 2);
  });
});