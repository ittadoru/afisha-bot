import { LoaderCircle, LogOut, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { appConfig } from "@/config";

export interface AccountProfile {
  public_id: string;
  display_name: string;
  bio: string | null;
  selected_city_id: string | null;
  age_confirmed: boolean;
  city_name?: string | null;
  avatar_url?: string | null;
  version?: number;
  next_name_change_at?: string | null;
  organizer_status?: "new" | "trusted";
  successful_events?: number;
  upcoming_count?: number;
  completed_count?: number;
}

interface SessionResponse {
  profile: AccountProfile;
  csrf_token: string;
  created: boolean;
}

type AuthState =
  | { status: "loading" }
  | { status: "outside-telegram" }
  | { status: "error" }
  | { status: "age"; profile: AccountProfile; csrfToken: string }
  | { status: "ready"; profile: AccountProfile; csrfToken: string };

const API_BASE = appConfig.apiBaseUrl;

export function MiniAppAuth({ children }: { children: (props: { profile: AccountProfile; csrfToken: string; updateProfile: (profile: AccountProfile) => void; logout: () => Promise<void> }) => React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const exchangeTelegramSession = async () => {
    const initData = window.Telegram?.WebApp?.initData;
    if (!initData) {
      setState({ status: "outside-telegram" });
      return;
    }
    const bootstrap = await fetch(`${API_BASE}/auth/mini/bootstrap`, { method: "POST", credentials: "include", headers: { Accept: "application/json" } });
    if (!bootstrap.ok) throw new Error("bootstrap failed");
    const { nonce } = await parseJson<{ nonce: string }>(bootstrap);
    const exchange = await fetch(`${API_BASE}/auth/mini/exchange`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ init_data: initData, nonce }),
    });
    if (!exchange.ok) throw new Error("exchange failed");
    const session = await parseJson<SessionResponse>(exchange);
    setState(session.profile.age_confirmed ? { status: "ready", profile: session.profile, csrfToken: session.csrf_token } : { status: "age", profile: session.profile, csrfToken: session.csrf_token });
  };

  const authenticate = async () => {
    setState({ status: "loading" });
    try {
      const existing = await fetch(`${API_BASE}/account/me`, { credentials: "include", headers: { Accept: "application/json" } });
      if (!existing.ok) {
        await exchangeTelegramSession();
        return;
      }
      const profile = await parseJson<AccountProfile>(existing);
      const csrfToken = existing.headers.get("X-Afisha-CSRF");
      if (!csrfToken) {
        await exchangeTelegramSession();
        return;
      }
      setState(profile.age_confirmed ? { status: "ready", profile, csrfToken } : { status: "age", profile, csrfToken });
    } catch {
      setState({ status: "error" });
    }
  };

  const confirmAge = async () => {
    if (state.status !== "age") return;
    try {
      const response = await fetch(`${API_BASE}/account/age-consent`, {
        method: "POST",
        credentials: "include",
        headers: { "X-Afisha-CSRF": state.csrfToken, Accept: "application/json" },
      });
      if (!response.ok) throw new Error("age confirmation failed");
      const profile = await parseJson<AccountProfile>(response);
      setState({ status: "ready", profile, csrfToken: state.csrfToken });
    } catch {
      setState({ status: "error" });
    }
  };

  const logout = async () => {
    if (state.status !== "ready" && state.status !== "age") return;
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include", headers: { "X-Afisha-CSRF": state.csrfToken } });
    setState({ status: "outside-telegram" });
  };

  useEffect(() => { void authenticate(); }, []);

  const updateProfile = (profile: AccountProfile) => {
    setState((current) => current.status === "ready" ? { ...current, profile } : current);
  };

  if (state.status === "loading") return <AuthScreen icon={<LoaderCircle className="spin" />} title="Входим через Telegram" text="Проверяем безопасный вход…" />;
  if (state.status === "outside-telegram") return <AuthScreen icon={<ShieldCheck />} title="Откройте приложение через Telegram" text="Вход доступен только из Mini App. Откройте бота и нажмите кнопку приложения." />;
  if (state.status === "error") return <AuthScreen icon={<ShieldCheck />} title="Не получилось войти" text="Закройте Mini App, откройте его снова и повторите попытку." action={<Button onClick={() => void authenticate()}>Повторить</Button>} />;
  if (state.status === "age") return <AuthScreen icon={<ShieldCheck />} title="Подтвердите возраст" text="Чтобы пользоваться Афишей, вам должно быть не меньше 14 лет." action={<div className="auth-actions"><Button onClick={() => void confirmAge()}>Мне исполнилось 14 лет</Button><Button variant="outline" onClick={() => void logout()}><LogOut /> Выйти</Button></div>} />;
  return <>{children({ profile: state.profile, csrfToken: state.csrfToken, updateProfile, logout })}</>;
}

function AuthScreen({ icon, title, text, action }: { icon: React.ReactNode; title: string; text: string; action?: React.ReactNode }) {
  return <main className="mini-app"><section className="centered-screen auth-screen" role="status"><span className="big-icon">{icon}</span><h1>{title}</h1><p>{text}</p>{action}</section></main>;
}

async function parseJson<T>(response: Response): Promise<T> {
  return await response.json() as T;
}
