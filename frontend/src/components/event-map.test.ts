import { describe, expect, it } from "vitest";

import { centralHalfBounds } from "./event-map";

describe("centralHalfBounds", () => {
  it("crops exactly 25 percent from every edge", () => {
    expect(centralHalfBounds({ west: 40, south: 10, east: 60, north: 30 })).toEqual([
      [45, 15],
      [55, 25],
    ]);
  });
});
