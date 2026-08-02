import { defineConfig } from "orval";

export default defineConfig({
  afisha: {
    input: { target: "./openapi/afisha.openapi.json" },
    output: {
      target: "./src/api/generated/afisha.ts",
      schemas: "./src/api/generated/models",
      client: "fetch",
      clean: true,
      mock: { generators: [{ type: "msw" }, { type: "faker" }] },
    },
  },
});
