import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import "@fontsource-variable/manrope";
import "cropperjs/dist/cropper.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "@/styles.css";

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
