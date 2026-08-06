import {
  Activity,
  CalendarClock,
  ClipboardCheck,
  History,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
  Sparkles,
  UserCog,
  Users,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Staff = { login: string; role: "admin" | "moderator" };
type Counts = {
  active_users: number;
  upcoming_events: number;
  pending_events: number;
  open_profile_reports: number;
  active_moderators: number;
};
type AuditEntry = {
  id: string;
  created_at: string;
  actor: string | null;
  action: string;
  result: "success" | "failure" | "blocked";
};
type AuditPage = { items: AuditEntry[]; next_before: string | null };
type View = "dashboard" | "special" | "audit";
type SpecialEvent = { id: string; title: string; starts_at: string; ends_at: string; city: string };
type CityOption = { id: string; slug: string; name: string; center_latitude: number; center_longitude: number };

const csrfHeader = "X-Afisha-Admin-CSRF";

export function AdminApp() {
  const [staff, setStaff] = useState<Staff | null>(null);
  const [csrf, setCsrf] = useState("");
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    void api<Staff>("/account/me").then(({ data, response }) => {
      setStaff(data);
      setCsrf(response.headers.get(csrfHeader) ?? "");
    }).catch(() => undefined).finally(() => setChecking(false));
  }, []);

  if (checking) return <AdminStatus text="Проверяем доступ…" />;
  if (!staff) {
    return <AdminLogin onLogin={(account, token) => { setStaff(account); setCsrf(token); }} />;
  }
  return <AdminShell staff={staff} csrf={csrf} onCsrf={setCsrf} onLogout={() => setStaff(null)} />;
}

function AdminLogin({ onLogin }: { onLogin: (staff: Staff, csrf: string) => void }) {
  const [login, setLogin] = useState("Atari");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const bootstrap = await api<{ csrf_token: string }>("/auth/bootstrap", { method: "POST" });
      const result = await api<{ account: Staff; csrf_token: string }>("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json", [csrfHeader]: bootstrap.data.csrf_token },
        body: JSON.stringify({ login, password }),
      });
      onLogin(result.data.account, result.data.csrf_token);
    } catch (reason) {
      setError(reason instanceof AdminApiError && reason.status === 429
        ? "Слишком много попыток. Попробуйте через 15 минут."
        : "Не удалось войти. Проверьте данные и попробуйте снова.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="admin-login-page">
      <section className="admin-login-card" aria-labelledby="admin-login-title">
        <div className="admin-mark"><ShieldCheck aria-hidden="true" /></div>
        <p className="admin-kicker">PODVVAL · УПРАВЛЕНИЕ</p>
        <h1 id="admin-login-title">Вход в панель</h1>
        <p className="admin-muted">Закрытая область для команды сервиса.</p>
        <form onSubmit={submit} className="admin-login-form">
          <label>Логин<input value={login} onChange={(event) => setLogin(event.target.value)} autoComplete="username" maxLength={64} required /></label>
          <label>Пароль<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" maxLength={256} required autoFocus /></label>
          {error && <p className="admin-form-error" role="alert">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? "Входим…" : "Войти"}</button>
        </form>
      </section>
    </main>
  );
}

function AdminShell({ staff, csrf, onCsrf, onLogout }: { staff: Staff; csrf: string; onCsrf: (value: string) => void; onLogout: () => void }) {
  const [view, setView] = useState<View>("dashboard");

  const logout = async () => {
    try { await api("/auth/logout", { method: "POST", headers: { [csrfHeader]: csrf } }); }
    finally { onLogout(); }
  };

  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <div className="admin-brand"><span><ShieldCheck /></span><div><strong>PODVVAL</strong><small>Панель управления</small></div></div>
        <nav aria-label="Разделы панели">
          <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}><LayoutDashboard />Главная</button>
          <button className={view === "special" ? "active" : ""} onClick={() => setView("special")}><Sparkles />Особые события</button>
          <button className={view === "audit" ? "active" : ""} onClick={() => setView("audit")}><History />История действий</button>
        </nav>
        <div className="admin-sidebar-footer">
          <div className="admin-person"><span>{staff.login.slice(0, 1).toUpperCase()}</span><div><strong>{staff.login}</strong><small>Администратор</small></div></div>
          <button onClick={() => void logout()}><LogOut />Выйти</button>
        </div>
      </aside>
      <main className="admin-content">
        {view === "dashboard" ? <Dashboard csrf={csrf} onCsrf={onCsrf} staff={staff} /> : view === "special" ? <SpecialEvents csrf={csrf} onCsrf={onCsrf} /> : <Audit csrf={csrf} onCsrf={onCsrf} />}
      </main>
    </div>
  );
}

function SpecialEvents({ csrf, onCsrf }: { csrf: string; onCsrf: (value: string) => void }) {
  const [items, setItems] = useState<SpecialEvent[] | null>(null);
  const [reason, setReason] = useState("plans_changed");
  const [cities, setCities] = useState<CityOption[]>([]);
  const [creating, setCreating] = useState(false);
  const [busyForm, setBusyForm] = useState(false);
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState({
    title: "",
    description: "",
    city_id: "",
    starts_at: "",
    ends_at: "",
    place: "",
    latitude: "",
    longitude: "",
  });
  const load = useCallback(async () => {
    const result = await api<{ items: SpecialEvent[] }>("/events/special");
    onCsrf(result.response.headers.get(csrfHeader) ?? "");
    setItems(result.data.items);
  }, [onCsrf]);
  useEffect(() => { void load().catch(() => setItems([])); }, [load]);
  useEffect(() => {
    void api<{ cities: CityOption[] }>("/geo/catalog")
      .then(({ data, response }) => {
        onCsrf(response.headers.get(csrfHeader) ?? "");
        setCities(data.cities);
        setForm((current) => ({ ...current, city_id: current.city_id || data.cities[0]?.id || "" }));
      })
      .catch(() => undefined);
  }, [onCsrf]);
  const setField = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const create = async (event: FormEvent) => {
    event.preventDefault();
    setBusyForm(true);
    setFormError("");
    try {
      await api("/events/special", {
        method: "POST",
        headers: { "Content-Type": "application/json", [csrfHeader]: csrf },
        body: JSON.stringify({
          title: form.title,
          description: form.description,
          city_id: form.city_id,
          starts_at: new Date(form.starts_at).toISOString(),
          ends_at: new Date(form.ends_at).toISOString(),
          place: form.place,
          latitude: form.latitude ? Number(form.latitude) : null,
          longitude: form.longitude ? Number(form.longitude) : null,
        }),
      });
      setForm({ title: "", description: "", city_id: form.city_id, starts_at: "", ends_at: "", place: "", latitude: "", longitude: "" });
      await load();
    } catch (reason) {
      setFormError(reason instanceof AdminApiError ? "Не удалось создать событие. Проверьте данные." : "Нет связи с сервером.");
    } finally {
      setBusyForm(false);
    }
  };
  const cancel = async (event: SpecialEvent) => {
    if (!window.confirm(`Отменить «${event.title}»?`)) return;
    await api(`/events/special/${event.id}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [csrfHeader]: csrf },
      body: JSON.stringify({ reason }),
    });
    await load();
  };
  return <section><header className="admin-page-header"><div><p>Общественные события</p><h1>Особые события</h1></div></header>
    {!creating ? <button className="admin-more" onClick={() => setCreating(true)}>Создать событие</button>
      : <form onSubmit={create} className="admin-create-form">
        <h2>Новое общественное событие</h2>
        <label>Название<input value={form.title} onChange={setField("title")} maxLength={60} required /></label>
        <label>Описание<textarea value={form.description} onChange={setField("description")} maxLength={1000} rows={4} required /></label>
        <label>Город<select value={form.city_id} onChange={setField("city_id")}>{cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}</select></label>
        <div className="admin-create-row">
          <label>Начало<input type="datetime-local" value={form.starts_at} onChange={setField("starts_at")} required /></label>
          <label>Конец<input type="datetime-local" value={form.ends_at} onChange={setField("ends_at")} required /></label>
        </div>
        <label>Место (необязательно)<input value={form.place} onChange={setField("place")} maxLength={500} placeholder="Например: парк Ак-Гёль" /></label>
        <div className="admin-create-row">
          <label>Широта (необязательно)<input type="number" step="any" value={form.latitude} onChange={setField("latitude")} placeholder="центр города" /></label>
          <label>Долгота (необязательно)<input type="number" step="any" value={form.longitude} onChange={setField("longitude")} placeholder="центр города" /></label>
        </div>
        {formError && <p className="admin-form-error" role="alert">{formError}</p>}
        <div className="admin-create-actions"><button type="submit" disabled={busyForm}>{busyForm ? "Публикуем…" : "Опубликовать"}</button><button type="button" className="admin-ghost" onClick={() => setCreating(false)}>Отмена</button></div>
      </form>}
    <label className="admin-inline-control">Причина отмены<select value={reason} onChange={(event) => setReason(event.target.value)}><option value="plans_changed">Планы изменились</option><option value="not_enough_participants">Не набралось участников</option><option value="venue_problem">Проблемы с местом</option><option value="unforeseen_circumstances">Непредвиденные обстоятельства</option></select></label>{items === null ? <AdminStatus text="Загружаем события…" /> : items.length ? <div className="admin-table-wrap"><table><thead><tr><th>Событие</th><th>Город</th><th>Начало</th><th /></tr></thead><tbody>{items.map((event) => <tr key={event.id}><td>{event.title}</td><td>{event.city}</td><td>{new Date(event.starts_at).toLocaleString("ru-RU")}</td><td><button className="admin-more" onClick={() => void cancel(event)}>Отменить</button></td></tr>)}</tbody></table></div> : <AdminEmpty title="Активных особых событий нет" text="Создайте первое общественное событие." />}</section>;
}

function Dashboard({ staff, onCsrf }: { csrf: string; onCsrf: (value: string) => void; staff: Staff }) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    void api<Counts>("/dashboard").then(({ data, response }) => {
      setCounts(data); onCsrf(response.headers.get(csrfHeader) ?? "");
    }).catch(() => setFailed(true));
  }, [onCsrf]);
  const cards = counts ? [
    ["Активные пользователи", counts.active_users, Users],
    ["Будущие события", counts.upcoming_events, CalendarClock],
    ["На проверке", counts.pending_events, ClipboardCheck],
    ["Открытые жалобы", counts.open_profile_reports, Activity],
    ["Активные модераторы", counts.active_moderators, UserCog],
  ] as const : [];
  return (
    <section>
      <header className="admin-page-header"><div><p>Обзор сервиса</p><h1>Добрый день, {staff.login}</h1></div><span className="admin-live"><i />Система работает</span></header>
      {failed ? <AdminEmpty title="Не удалось загрузить данные" text="Обновите страницу и попробуйте снова." /> : !counts ? <AdminStatus text="Загружаем показатели…" /> : <div className="admin-stat-grid">{cards.map(([label, value, Icon]) => <article className="admin-stat" key={label}><span><Icon /></span><p>{label}</p><strong>{value.toLocaleString("ru-RU")}</strong></article>)}</div>}
    </section>
  );
}

function Audit({ onCsrf }: { csrf: string; onCsrf: (value: string) => void }) {
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async (before?: string) => {
    setBusy(true); setFailed(false);
    try {
      const result = await api<AuditPage>(`/audit${before ? `?before=${encodeURIComponent(before)}` : ""}`);
      onCsrf(result.response.headers.get(csrfHeader) ?? "");
      setItems((current) => before ? [...current, ...result.data.items] : result.data.items);
      setNext(result.data.next_before);
    } catch { setFailed(true); } finally { setBusy(false); }
  }, [onCsrf]);
  useEffect(() => { void load(); }, [load]);
  return (
    <section>
      <header className="admin-page-header"><div><p>Безопасность</p><h1>История действий</h1></div></header>
      {failed && !items.length ? <AdminEmpty title="История недоступна" text="Обновите страницу и попробуйте снова." /> : !busy && !items.length ? <AdminEmpty title="Действий пока нет" text="Здесь появятся входы и административные изменения." /> : <div className="admin-table-wrap"><table><thead><tr><th>Время</th><th>Администратор</th><th>Действие</th><th>Результат</th></tr></thead><tbody>{items.map((entry) => <tr key={entry.id}><td>{new Date(entry.created_at).toLocaleString("ru-RU")}</td><td>{entry.actor ?? "Система"}</td><td>{actionLabel(entry.action)}</td><td><span className={`admin-result ${entry.result}`}>{resultLabel(entry.result)}</span></td></tr>)}</tbody></table>{next && <button className="admin-more" disabled={busy} onClick={() => void load(next)}>{busy ? "Загружаем…" : "Показать ещё"}</button>}</div>}
    </section>
  );
}

function AdminStatus({ text }: { text: string }) { return <main className="admin-status" role="status"><span /><p>{text}</p></main>; }
function AdminEmpty({ title, text }: { title: string; text: string }) { return <div className="admin-empty"><History /><h2>{title}</h2><p>{text}</p></div>; }
function actionLabel(action: string) { return ({ "staff.bootstrap": "Создан первый администратор", "staff.login_bootstrap": "Подготовлен вход", "staff.login": "Вход в панель", "staff.logout": "Выход из панели" } as Record<string, string>)[action] ?? action; }
function resultLabel(result: AuditEntry["result"]) { return result === "success" ? "Успешно" : result === "blocked" ? "Заблокировано" : "Отказ"; }

class AdminApiError extends Error { constructor(public status: number) { super("Admin request failed"); } }
async function api<T = undefined>(path: string, init?: RequestInit): Promise<{ data: T; response: Response }> {
  const response = await fetch(`/api/admin${path}`, { ...init, credentials: "same-origin", headers: { Accept: "application/json", ...init?.headers } });
  if (!response.ok) throw new AdminApiError(response.status);
  const data = response.status === 204 ? undefined : await response.json();
  return { data: data as T, response };
}
