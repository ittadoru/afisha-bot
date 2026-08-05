/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_MAP_STYLE_URL?: string;
  readonly VITE_USE_MOCKS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.svg?raw" {
  const content: string;
  export default content;
}

interface TelegramWebApp {
  initData: string;
  ready: () => void;
  expand: () => void;
  isVersionAtLeast?: (version: string) => boolean;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  colorScheme?: "light" | "dark";
  themeParams?: Record<string, string>;
  onEvent?: (event: "themeChanged", callback: () => void) => void;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  showConfirm?: (message: string, callback: (confirmed: boolean) => void) => void;
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}
