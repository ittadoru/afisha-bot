const DEFAULT_MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

export const appConfig = Object.freeze({
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  mapStyleUrl: import.meta.env.VITE_MAP_STYLE_URL ?? DEFAULT_MAP_STYLE,
  useMocks: import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === "true",
});
