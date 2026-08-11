import { Check, LogOut, MapPin, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { appConfig } from "@/config";

export interface AccountProfile {
  public_id: string;
  display_name: string;
  bio: string | null;
  selected_city_id: string | null;
  age_confirmed: boolean;
  city_name?: string | null;
  avatar_url?: string | null;
  avatar_thumbnail_url?: string | null;
  background_url?: string | null;
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
  | { status: "onboarding"; profile: AccountProfile; csrfToken: string }
  | { status: "ready"; profile: AccountProfile; csrfToken: string };

const API_BASE = appConfig.apiBaseUrl;

export function MiniAppAuth({ children }: { children: (props: { profile: AccountProfile; csrfToken: string; updateProfile: (profile: AccountProfile) => void; logout: () => Promise<void> }) => React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [pending, setPending] = useState(false);

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
    setState(session.profile.age_confirmed && session.profile.selected_city_id ? { status: "ready", profile: session.profile, csrfToken: session.csrf_token } : { status: "onboarding", profile: session.profile, csrfToken: session.csrf_token });
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
      setState(profile.age_confirmed && profile.selected_city_id ? { status: "ready", profile, csrfToken } : { status: "onboarding", profile, csrfToken });
    } catch {
      setState({ status: "error" });
    }
  };

  const logout = async () => {
    if (state.status !== "ready" && state.status !== "onboarding") return;
    setPending(true);
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include", headers: { "X-Afisha-CSRF": state.csrfToken } });
      setState({ status: "outside-telegram" });
    } finally {
      setPending(false);
    }
  };

  useEffect(() => { void authenticate(); }, []);

  const updateProfile = (profile: AccountProfile) => {
    setState((current) => current.status === "ready" ? { ...current, profile } : current);
  };

  if (pending) return <LoadingScreen />;
  if (state.status === "loading") return <LoadingScreen />;
  if (state.status === "outside-telegram") return <AuthScreen icon={<ShieldCheck />} title="Откройте приложение через Telegram" text="Вход доступен только из Mini App. Откройте бота и нажмите кнопку приложения." />;
  if (state.status === "error") return <AuthScreen icon={<ShieldCheck />} title="Не получилось войти" text="Закройте Mini App, откройте его снова и повторите попытку." action={<Button onClick={() => void authenticate()}>Повторить</Button>} />;
  if (state.status === "onboarding") return <Onboarding profile={state.profile} csrfToken={state.csrfToken} pending={pending} onDone={(profile) => setState({ status: "ready", profile, csrfToken: state.csrfToken })} onLogout={logout} />;
  return <>{children({ profile: state.profile, csrfToken: state.csrfToken, updateProfile, logout })}</>;
}

type City = { id: string; name: string };

function Onboarding({ profile, csrfToken, pending, onDone, onLogout }: { profile: AccountProfile; csrfToken: string; pending: boolean; onDone: (profile: AccountProfile) => void; onLogout: () => Promise<void> }) {
  const [cities, setCities] = useState<City[]>([]);
  const [cityId, setCityId] = useState(profile.selected_city_id ?? "");
  const [accepted, setAccepted] = useState(profile.age_confirmed);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void fetch(`${API_BASE}/geo/catalog`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        return await parseJson<{ cities: City[] }>(response);
      })
      .then((catalog) => setCities(catalog.cities))
      .catch(() => setError("Не удалось загрузить города. Повторите попытку."))
      .finally(() => setLoading(false));
  }, []);

  const submit = async () => {
    if (!cityId || !accepted || pending || saving) return;
    setError("");
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/account/onboarding`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, Accept: "application/json" },
        body: JSON.stringify({ selected_city_id: cityId, accepted_age_rule: true, profile_version: profile.version ?? 1 }),
      });
      if (!response.ok) throw new Error(String(response.status));
      onDone(await parseJson<AccountProfile>(response));
    } catch (reason) {
      setError(reason instanceof Error && reason.message === "422" ? "Этот город сейчас недоступен." : "Не удалось сохранить выбор. Повторите попытку.");
    } finally {
      setSaving(false);
    }
  };

  return <main className="mini-app"><section className="onboarding-screen" aria-labelledby="onboarding-title"><span className="big-icon"><MapPin /></span><p className="section-kicker">Добро пожаловать</p><h1 id="onboarding-title">Есть куда пойти.<br />Есть с кем.</h1><p>Выберите город и подтвердите возраст — это займёт минуту.</p><fieldset disabled={loading || pending || saving}><legend>Ваш город</legend><div className="onboarding-city-list">{cities.map((city) => <label className={`onboarding-city${cityId === city.id ? " selected" : ""}`} key={city.id} onClick={() => setCityId(city.id)}><input type="radio" name="onboarding-city" value={city.id} checked={cityId === city.id} onChange={() => setCityId(city.id)} /><span>{city.name}</span>{cityId === city.id && <Check aria-hidden="true" />}</label>)}</div><p className="onboarding-other">Другой город появится в приложении позже.</p></fieldset><label className="onboarding-age"><input type="checkbox" checked={accepted} disabled={profile.age_confirmed || pending || saving} onChange={(event) => setAccepted(event.target.checked)} /><span>Мне исполнилось 14 лет</span></label>{error && <p className="form-error" role="alert">{error}</p>}<div className="auth-actions"><Button disabled={loading || pending || saving || !cityId || !accepted} onClick={() => void submit()}>{saving ? "Сохраняем…" : "Ехала →"}</Button><Button variant="outline" disabled={pending || saving} onClick={() => void onLogout()}><LogOut /> Выйти</Button></div></section></main>;
}

function AuthScreen({ icon, title, text, action }: { icon: React.ReactNode; title: string; text: string; action?: React.ReactNode }) {
  return <main className="mini-app"><section className="centered-screen auth-screen" role="status"><span className="big-icon">{icon}</span><h1>{title}</h1><p>{text}</p>{action}</section></main>;
}

async function parseJson<T>(response: Response): Promise<T> {
  return await response.json() as T;
}
