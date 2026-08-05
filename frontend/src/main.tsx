import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import "@fontsource-variable/manrope";
import "cropperjs/dist/cropper.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "@/styles.css";

function initializeTelegramMiniApp(): void {
  const webApp = window.Telegram?.WebApp;
  const applyTheme = () => {
    const isMiniApp = window.location.pathname.startsWith("/app");
    const isDark = isMiniApp && webApp?.colorScheme === "dark";
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    const background = isDark ? "#111816" : "#f8f4ea";
    webApp?.setHeaderColor?.(background);
    webApp?.setBackgroundColor?.(background);
  };
  applyTheme();
  if (!webApp) return;

  // Telegram opens Mini Apps as a bottom sheet by default. Calling expand()
  // immediately makes the app use the maximum available WebView height.
  webApp.ready();
  webApp.expand();
  webApp.onEvent?.("themeChanged", applyTheme);
}

initializeTelegramMiniApp();

async function enableMocks(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_USE_MOCKS !== "true") return;
  const { worker } = await import("@/mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

await enableMocks();

const root = document.getElementById("root");
if (!root) throw new Error("Root element is missing");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
