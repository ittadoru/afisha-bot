import { describe, expect, it } from "vitest";

import { cropFractions } from "./photo-crop";

describe("cropFractions", () => {
  it("maps the full 4:3 frame of a landscape 4:3 photo", () => {
    const box = { x: 0, y: 0, width: 4000, height: 3000 };
    const image = { naturalWidth: 4000, naturalHeight: 3000 };

    const crop = cropFractions(box, image);

    expect(crop.x).toBeCloseTo(0);
    expect(crop.y).toBeCloseTo(0);
    expect(crop.width).toBeCloseTo(1);
    expect(crop.height).toBeCloseTo(1);
    expect((crop.width * 4000) / (crop.height * 3000)).toBeCloseTo(4 / 3, 2);
  });

  it("maps a 4:3 frame cropped from a square source", () => {
    const box = { x: 0, y: 150, width: 1200, height: 900 };
    const image = { naturalWidth: 1200, naturalHeight: 1200 };

    const crop = cropFractions(box, image);

    expect(crop.x).toBeCloseTo(0);
    expect(crop.y).toBeCloseTo(0.125);
    expect(crop.width).toBeCloseTo(1);
    expect(crop.height).toBeCloseTo(0.75);
    expect((crop.width * 1200) / (crop.height * 1200)).toBeCloseTo(4 / 3, 2);
  });

  it("maps a 4:3 frame from a portrait 3:4 photo to a horizontal box", () => {
    const box = { x: 0, y: 875, width: 3000, height: 2250 };
    const image = { naturalWidth: 3000, naturalHeight: 4000 };

    const crop = cropFractions(box, image);

    expect(crop.x).toBeCloseTo(0);
    expect(crop.y).toBeCloseTo(0.21875);
    expect(crop.width).toBeCloseTo(1);
    expect(crop.height).toBeCloseTo(0.5625);
    expect(crop.x + crop.width).toBeLessThanOrEqual(1.000001);
    expect(crop.y + crop.height).toBeLessThanOrEqual(1.000001);
    expect((crop.width * 3000) / (crop.height * 4000)).toBeCloseTo(4 / 3, 2);
  });

  it("produces a zero-size box for degenerate inputs", () => {
    const crop = cropFractions({ x: 0, y: 0, width: 0, height: 0 }, { naturalWidth: 4000, naturalHeight: 3000 });
    expect(crop.width).toBe(0);
    expect(crop.height).toBe(0);
  });
});