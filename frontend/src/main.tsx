import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import "@fontsource-variable/manrope";
import "@/styles.css";
import "@/material-system.css";

if (import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === "true" && !window.Telegram) {
  window.Telegram = { WebApp: { initData: "mock-telegram-init-data", ready: () => undefined, expand: () => undefined } };
}

function initializeTelegramMiniApp(): void {
  const webApp = window.Telegram?.WebApp;
  document.documentElement.dataset.miniApp = String(window.location.pathname.startsWith("/app"));
  document.documentElement.dataset.uiScope = window.location.hostname === "admin.podvval.xyz" ? "admin" : "consumer";
  const applyTheme = () => {
    document.documentElement.dataset.theme = "light";
    document.documentElement.style.colorScheme = "light";
    const background = "#f7f3e8";
    webApp?.setHeaderColor?.(background);
    webApp?.setBackgroundColor?.(background);
  };
  applyTheme();
  if (!webApp) return;

  webApp.ready();
  webApp.disableVerticalSwipes?.();
  const syncFullscreen = () => {
    document.documentElement.dataset.fullscreen = String(Boolean(webApp.isFullscreen));
  };
  const expand = () => webApp.expand();
  webApp.onEvent?.("fullscreenFailed", expand);
  try {
    if (webApp.isVersionAtLeast?.("8.0") && webApp.requestFullscreen) webApp.requestFullscreen();
    else expand();
  } catch { expand(); }
  syncFullscreen();
  const setInset = (prefix: string, inset: { top: number; bottom: number; left: number; right: number } | undefined) => {
    if (!inset) return;
    const root = document.documentElement.style;
    root.setProperty(`${prefix}-top`, `${inset.top}px`);
    root.setProperty(`${prefix}-bottom`, `${inset.bottom}px`);
    root.setProperty(`${prefix}-left`, `${inset.left}px`);
    root.setProperty(`${prefix}-right`, `${inset.right}px`);
  };
  const applySafeArea = () => {
    setInset("--tg-safe", webApp.safeAreaInset);
    setInset("--tg-content-safe", webApp.contentSafeAreaInset);
  };
  const applyViewport = () => {
    const viewport = window.visualViewport;
    const height = viewport?.height ?? webApp.viewportStableHeight ?? webApp.viewportHeight ?? window.innerHeight;
    document.documentElement.style.setProperty("--app-height", `${Math.round(height)}px`);
    document.documentElement.dataset.keyboardOpen = String(Boolean(viewport && window.innerHeight - viewport.height > 120));
    window.dispatchEvent(new Event("miniappviewportchange"));
  };
  applySafeArea();
  webApp.onEvent?.("themeChanged", applyTheme);
  webApp.onEvent?.("safeAreaChanged", applySafeArea);
  webApp.onEvent?.("contentSafeAreaChanged", applySafeArea);
  webApp.onEvent?.("viewportChanged", applyViewport);
  webApp.onEvent?.("fullscreenChanged", () => { syncFullscreen(); applySafeArea(); applyViewport(); requestAnimationFrame(() => { applySafeArea(); applyViewport(); }); });
  window.visualViewport?.addEventListener("resize", applyViewport);
  window.visualViewport?.addEventListener("scroll", applyViewport);
  applyViewport();
  requestAnimationFrame(() => { syncFullscreen(); applySafeArea(); applyViewport(); });
}

initializeTelegramMiniApp();

// Keep native map gestures while preventing page-level pinch/double-tap zoom.
document.addEventListener("gesturestart", (event) => {
  if (!(event.target as Element | null)?.closest(".maplibregl-map")) event.preventDefault();
}, { passive: false });
let lastTouchEnd = 0;
document.addEventListener("touchend", (event) => {
  if ((event.target as Element | null)?.closest(".maplibregl-map")) return;
  const now = Date.now();
  if (now - lastTouchEnd < 300) event.preventDefault();
  lastTouchEnd = now;
}, { passive: false });

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
