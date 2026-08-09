import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// The Mini App is route-split. Cold Docker/CI workers can need more than the
// browser-oriented one second default to transform and resolve its lazy chunk.
configure({ asyncUtilTimeout: 5_000 });
