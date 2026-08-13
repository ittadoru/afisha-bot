import {
  Activity,
  CalendarClock,
  ClipboardCheck,
  History,
  LayoutDashboard,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  MapPinned,
  UserCog,
  Users,
  Flag,
  Gavel,
  X,
} from "lucide-react";
import "@/admin.css";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertDialog } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";

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
type View = "dashboard" | "moderation" | "streets" | "special" | "audit";
type SpecialEvent = { id: string; title: string; starts_at: string; ends_at: string; city: string };
type CityOption = { id: string; slug: string; name: string; center_latitude: number; center_longitude: number };
type CategoryOption = { id: string; slug: string; name: string; organizer_selectable: boolean };
type Review = { id: string; event_id: string; event_revision_id: string; submitted_at: string; title: string; starts_at: string; city: string; public_id: string; display_name: string };
type ReviewDetail = Review & { description: string; ends_at: string; normalized_address: string; organizer_address: string | null; organizer_street: string | null; organizer_place: string | null; street_name: string | null; landmark: string | null; address_visibility: string; street_anchor_id: string | null; street_anchor_name: string | null; latitude: number; longitude: number; capacity: number | null; category: string; organizer_status: string; successful_events: number; photo_url: string };
type StreetAnchor = { id: string; city_id: string; display_name: string; source: "nominatim" | "staff"; geometry_version: number; updated_at: string; latitude: number; longitude: number; active_event_count: number };
type SystemMetrics = { collected_at: string; disk: { size_bytes: number; used_bytes: number; available_bytes: number }; memory: { total_bytes: number; used_bytes: number; available_bytes: number }; cpu: { load_1: number; load_5: number; load_15: number }; uptime_seconds: number; containers: Array<{ name: string; cpu_percent: number; memory_usage: string; memory_limit: string }> };
type ImageBreakdown = { name: string; file_count: number; total_bytes: number; percent?: number };
type ImageEstimate = { quality: number; sample_file_count: number; sample_bytes: number; sample_saved_bytes: number; sample_saved_percent: number; eligible_bytes: number; estimated_saved_bytes: number };
type ImageAnalysis = { collected_at: string; source: "database"; file_count: number; total_bytes: number; permanent_file_count: number; permanent_bytes: number; temporary_file_count: number; temporary_bytes: number; formats: ImageBreakdown[]; purposes: ImageBreakdown[]; directories: ImageBreakdown[]; estimate_status: "idle" | "queued" | "running" | "completed" | "failed"; estimate_job_id: string | null; estimate_collected_at: string | null; estimate: ImageEstimate | null };
type ModerationQueue = "events" | "reports" | "appeals";
type ModerationCounts = { events: number; reports: number; appeals: number };
type ModerationCase = { public_id: string; subject_type: string; subject_component: string | null; target_title: string | null; priority: string; version: number; created_at: string; updated_at: string; reason_code: string | null; appeal_created_at: string | null; appeal_status: string | null };
type CaseAction = "dismiss" | "hide_component" | "hold_for_correction" | "hide_subject" | "upheld" | "reversed";
type ModerationCaseDetail = ModerationCase & { status: string; explanation: string | null; previous_violations: number; subject?: Record<string, unknown> | null; evidence_snapshot?: Record<string, unknown> | null; target: { subject_type: string; component: string; subject_id: string; title: string | null; owner_name: string | null }; evidence: { schema_version: number; component: string; value: string | null; owner_name?: string | null; context_title?: string | null; captured_at: string }; current_state: Record<string, unknown> | null; evidence_state: "current" | "changed"; available_actions: CaseAction[]; timeline: Array<{ event_type: string; public_label: string; created_at: string }>; decisions: Array<{ decision_type: string; subject_component: string | null; staff_note: string; actor: string; created_at: string }>; appeal: { status: string; explanation: string; created_at: string } | null };

const csrfHeader = "X-Afisha-Admin-CSRF";

export function AdminApp() {
  const [staff, setStaff] = useState<Staff | null>(null);
  const [csrf, setCsrf] = useState("");
  const [checking, setChecking] = useState(true);
  const [expiredNotice, setExpiredNotice] = useState("");
  const adoptCsrf = useCallback((token: string) => { if (token) setCsrf(token); }, []);
  const renewCsrf = useCallback(async () => {
    const result = await api<Staff>("/account/me");
    const token = result.response.headers.get(csrfHeader);
    if (!token) throw new AdminApiError(401);
    setStaff(result.data);
    setCsrf(token);
    return token;
  }, []);
  const expire = useCallback(() => {
    setExpiredNotice("Сессия истекла. Войдите заново.");
    setStaff(null);
  }, []);
  const signIn = useCallback((account: Staff, token: string) => {
    setExpiredNotice("");
    setStaff(account);
    setCsrf(token);
  }, []);

  useEffect(() => {
    void api<Staff>("/account/me").then(({ data, response }) => {
      setStaff(data);
      adoptCsrf(response.headers.get(csrfHeader) ?? "");
    }).catch((error) => {
      if (error instanceof AdminApiError && error.status === 401) setExpiredNotice("Сессия истекла. Войдите заново.");
    }).finally(() => setChecking(false));
  }, []);

  if (checking) return <AdminFullScreenStatus text="Проверяем доступ…" />;
  if (!staff) {
    return <AdminLogin notice={expiredNotice} onLogin={signIn} />;
  }
  return <AdminShell staff={staff} csrf={csrf} onCsrf={adoptCsrf} renewCsrf={renewCsrf} onExpire={expire} onLogout={() => setStaff(null)} />;
}

function AdminLogin({ notice, onLogin }: { notice: string; onLogin: (staff: Staff, csrf: string) => void }) {
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

  if (busy) return <AdminFullScreenStatus text="Входим…" />;

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
          {notice && !error && <p className="admin-form-error" role="alert">{notice}</p>}
          <button type="submit" disabled={busy}>Войти</button>
        </form>
      </section>
    </main>
  );
}

function AdminShell({ staff, csrf, onCsrf, renewCsrf, onExpire, onLogout }: { staff: Staff; csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string>; onExpire: () => void; onLogout: () => void }) {
  const requestedView = new URLSearchParams(window.location.search).get("view") as View | null;
  const [view, setViewState] = useState<View>(requestedView && ["dashboard", "moderation", "streets", "special", "audit"].includes(requestedView) ? requestedView : "dashboard");
  const setView = (next: View) => {
    setViewState(next);
    const url = new URL(window.location.href);
    url.searchParams.set("view", next);
    if (next !== "moderation") url.searchParams.delete("queue");
    window.history.replaceState(null, "", url);
  };

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
          <button className={view === "moderation" ? "active" : ""} onClick={() => setView("moderation")}><ClipboardCheck />Модерация</button>
          <button className={view === "streets" ? "active" : ""} onClick={() => setView("streets")}><MapPinned />Улицы</button>
          <button className={view === "special" ? "active" : ""} onClick={() => setView("special")}><Sparkles />Общественные события</button>
          <button className={view === "audit" ? "active" : ""} onClick={() => setView("audit")}><History />История действий</button>
        </nav>
        <div className="admin-sidebar-footer">
          <div className="admin-person"><span>{staff.login.slice(0, 1).toUpperCase()}</span><div><strong>{staff.login}</strong><small>Администратор</small></div></div>
          <button onClick={() => void logout()}><LogOut />Выйти</button>
        </div>
      </aside>
      <main className="admin-content">
        {view === "dashboard" ? <Dashboard csrf={csrf} onCsrf={onCsrf} renewCsrf={renewCsrf} onExpire={onExpire} staff={staff} /> : view === "moderation" ? <Moderation csrf={csrf} onCsrf={onCsrf} renewCsrf={renewCsrf} onExpire={onExpire} /> : view === "streets" ? <Streets csrf={csrf} onExpire={onExpire} /> : view === "special" ? <SpecialEvents csrf={csrf} onCsrf={onCsrf} onExpire={onExpire} /> : <Audit csrf={csrf} onCsrf={onCsrf} onExpire={onExpire} />}
      </main>
    </div>
  );
}

function SpecialEvents({ csrf, onCsrf, onExpire }: { csrf: string; onCsrf: (value: string) => void; onExpire: () => void }) {
  const [items, setItems] = useState<SpecialEvent[] | null>(null);
  const [reason, setReason] = useState("plans_changed");
  const [cities, setCities] = useState<CityOption[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [creating, setCreating] = useState(false);
  const [busyForm, setBusyForm] = useState(false);
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState({
    title: "",
    description: "",
    city_id: "",
    category_id: "",
    start_date: "",
    start_time: "",
    end_date: "",
    end_time: "",
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
    void fetch("/api/geo/catalog", { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(async (response) => { if (!response.ok) throw new Error("catalog unavailable"); return await response.json() as { cities: CityOption[]; categories: CategoryOption[] }; })
      .then((data) => {
        setCities(data.cities);
        const selectable = data.categories.filter((item) => item.organizer_selectable && !["special", "cinema", "music"].includes(item.slug));
        setCategories(selectable);
        setForm((current) => ({ ...current, city_id: current.city_id || data.cities[0]?.id || "", category_id: current.category_id || selectable[0]?.id || "" }));
      })
      .catch(() => undefined);
  }, [onCsrf]);
  const setField = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const create = async (event: FormEvent) => {
    event.preventDefault();
    setFormError("");
    const startsAt = buildLocalIso(form.start_date, form.start_time);
    const endsAt = buildLocalIso(form.end_date, form.end_time);
    const latitude = coerceCoordinate(form.latitude, -90, 90, "Широта");
    const longitude = coerceCoordinate(form.longitude, -180, 180, "Долгота");
    if (!startsAt) { setFormError("Укажите дату и время начала — дату выберите в календаре, а время (например, 12:30) — в соседнем поле."); return; }
    if (!endsAt) { setFormError("Укажите дату и время конца — так же, как начало."); return; }
    if (endsAt <= startsAt) { setFormError("Конец события должен быть позже начала."); return; }
    if (latitude.error) { setFormError(latitude.error); return; }
    if (longitude.error) { setFormError(longitude.error); return; }
    setBusyForm(true);
    try {
      await api("/events/community", {
        method: "POST",
        headers: { "Content-Type": "application/json", [csrfHeader]: csrf },
        body: JSON.stringify({
          title: form.title,
          description: form.description,
          city_id: form.city_id,
          category_id: form.category_id,
          starts_at: startsAt,
          ends_at: endsAt,
          place: form.place,
          latitude: latitude.value,
          longitude: longitude.value,
        }),
      });
      setForm({ title: "", description: "", city_id: form.city_id, category_id: form.category_id, start_date: "", start_time: "", end_date: "", end_time: "", place: "", latitude: "", longitude: "" });
      await load();
    } catch (reason) {
      if (reason instanceof AdminApiError && reason.status === 401) { onExpire(); return; }
      setFormError(reason instanceof AdminApiError ? "Не удалось создать событие. Проверьте данные." : "Нет связи с сервером.");
    } finally {
      setBusyForm(false);
    }
  };
  const cancel = async (event: SpecialEvent) => {
    if (!window.confirm(`Отменить «${event.title}»?`)) return;
    try {
      await api(`/events/special/${event.id}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json", [csrfHeader]: csrf },
        body: JSON.stringify({ reason }),
      });
      await load();
    } catch (error) {
      if (error instanceof AdminApiError && error.status === 401) onExpire();
      else setFormError("Не удалось отменить событие. Попробуйте ещё раз.");
    }
  };
  return <section><header className="admin-page-header"><div><p>Только для staff</p><h1>Общественные события</h1></div></header>
    {!creating ? <button className="admin-more" onClick={() => setCreating(true)}>Создать событие</button>
      : <form onSubmit={create} className="admin-create-form">
        <h2>Новое общественное событие</h2>
        <label>Название<input value={form.title} onChange={setField("title")} maxLength={60} required /></label>
        <label>Описание<textarea value={form.description} onChange={setField("description")} maxLength={1000} rows={4} required /></label>
        <label>Город<select value={form.city_id} onChange={setField("city_id")}>{cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}</select></label>
        <label>Категория<select value={form.category_id} onChange={setField("category_id")} required>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <div className="admin-create-row">
          <label>Дата начала<input type="date" value={form.start_date} onChange={setField("start_date")} required /></label>
          <label>Время начала<input type="time" value={form.start_time} onChange={setField("start_time")} required /></label>
        </div>
        <div className="admin-create-row">
          <label>Дата конца<input type="date" value={form.end_date} onChange={setField("end_date")} required /></label>
          <label>Время конца<input type="time" value={form.end_time} onChange={setField("end_time")} required /></label>
        </div>
        <label>Место (необязательно)<input value={form.place} onChange={setField("place")} maxLength={500} placeholder="Например: парк Ак-Гёль" /></label>
        <div className="admin-create-row">
          <label>Широта (необязательно)<input type="text" inputMode="decimal" value={form.latitude} onChange={setField("latitude")} placeholder="например: 46,58 или 46.58" /></label>
          <label>Долгота (необязательно)<input type="text" inputMode="decimal" value={form.longitude} onChange={setField("longitude")} placeholder="например: 30,35 или 30.35" /></label>
        </div>
        {formError && <p className="admin-form-error" role="alert">{formError}</p>}
        <div className="admin-create-actions"><button type="submit" disabled={busyForm}>{busyForm ? "Публикуем…" : "Опубликовать"}</button><button type="button" className="admin-ghost" onClick={() => setCreating(false)}>Отмена</button></div>
      </form>}
    <label className="admin-inline-control">Причина отмены<select value={reason} onChange={(event) => setReason(event.target.value)}><option value="plans_changed">Планы изменились</option><option value="not_enough_participants">Не набралось участников</option><option value="venue_problem">Проблемы с местом</option><option value="unforeseen_circumstances">Непредвиденные обстоятельства</option></select></label>{items === null ? <AdminStatus text="Загружаем события…" /> : items.length ? <div className="admin-table-wrap"><table><thead><tr><th>Событие</th><th>Город</th><th>Начало</th><th /></tr></thead><tbody>{items.map((event) => <tr key={event.id}><td>{event.title}</td><td>{event.city}</td><td>{new Date(event.starts_at).toLocaleString("ru-RU")}</td><td><button className="admin-more" onClick={() => void cancel(event)}>Отменить</button></td></tr>)}</tbody></table></div> : <AdminEmpty title="Активных особых событий нет" text="Создайте первое общественное событие." />}</section>;
}

function buildLocalIso(date: string, time: string): string | null {
  if (!date || !time) return null;
  const value = new Date(`${date}T${time}`);
  return Number.isNaN(value.getTime()) ? null : value.toISOString();
}

function coerceCoordinate(raw: string, min: number, max: number, label: string): { value: number | null; error: string } {
  const text = raw.trim().replace(",", ".");
  if (!text) return { value: null, error: "" };
  const value = Number(text);
  if (!Number.isFinite(value)) return { value: null, error: `${label}: введите число через точку или запятую (например, 46,58).` };
  if (value < min || value > max) return { value: null, error: `${label}: значение вне допустимого диапазона (от ${min} до ${max}).` };
  return { value, error: "" };
}

function Dashboard({ staff, csrf, onCsrf, renewCsrf, onExpire }: { csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string>; onExpire: () => void; staff: Staff }) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [failed, setFailed] = useState(false);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [metricsFailed, setMetricsFailed] = useState(false);
  const [metricsRefreshing, setMetricsRefreshing] = useState(false);
  const [images, setImages] = useState<ImageAnalysis | null>(null);
  const [imagesLoading, setImagesLoading] = useState(true);
  const [imagesRefreshing, setImagesRefreshing] = useState(false);
  const [estimateSubmitting, setEstimateSubmitting] = useState(false);
  const [imagesError, setImagesError] = useState("");
  useEffect(() => {
    void api<Counts>("/dashboard").then(({ data, response }) => {
      setCounts(data); onCsrf(response.headers.get(csrfHeader) ?? "");
    }).catch((error) => { if (error instanceof AdminApiError && error.status === 401) onExpire(); else setFailed(true); });
  }, [onCsrf, onExpire]);
  const loadMetrics = useCallback(async () => {
    try { const result = await api<SystemMetrics>("/system/metrics"); setMetrics(result.data); onCsrf(result.response.headers.get(csrfHeader) ?? ""); setMetricsFailed(false); }
    catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); else setMetricsFailed(true); }
  }, [onCsrf, onExpire]);
  const refreshMetrics = async () => {
    setMetricsRefreshing(true); setMetricsFailed(false);
    const request = async (token: string) => await api<SystemMetrics>("/system/metrics/refresh", { method: "POST", headers: { [csrfHeader]: token } });
    try {
      let result: { data: SystemMetrics; response: Response };
      try { result = await request(csrf); }
      catch (error) { if (!(error instanceof AdminApiError) || error.status !== 401) throw error; result = await request(await renewCsrf()); }
      setMetrics(result.data); onCsrf(result.response.headers.get(csrfHeader) ?? "");
    } catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); else setMetricsFailed(true); } finally { setMetricsRefreshing(false); }
  };
  useEffect(() => {
    void loadMetrics();
    void api<ImageAnalysis>("/media/analysis").then(({ data, response }) => { setImages(data); onCsrf(response.headers.get(csrfHeader) ?? ""); }).catch(() => undefined).finally(() => setImagesLoading(false));
  }, [loadMetrics, onCsrf]);
  const refreshImages = async () => {
    setImagesRefreshing(true); setImagesError("");
    const request = async (token: string) => await api<ImageAnalysis>("/media/analysis/refresh", { method: "POST", headers: { [csrfHeader]: token } });
    try {
      let result: { data: ImageAnalysis; response: Response };
      try { result = await request(csrf); } catch (error) { if (!(error instanceof AdminApiError) || error.status !== 401) throw error; result = await request(await renewCsrf()); }
      setImages(result.data); onCsrf(result.response.headers.get(csrfHeader) ?? "");
    } catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); else setImagesError("Не удалось собрать отчёт. Повторите попытку."); } finally { setImagesRefreshing(false); }
  };
  const estimateImages = async () => {
    setEstimateSubmitting(true); setImagesError("");
    const request = async (token: string) => await api<{ job_id: string }>("/media/analysis/estimate", { method: "POST", headers: { [csrfHeader]: token } });
    try {
      try { await request(csrf); } catch (error) { if (!(error instanceof AdminApiError) || error.status !== 401) throw error; await request(await renewCsrf()); }
      setImages((current) => current ? { ...current, estimate_status: "queued", estimate: null } : current);
    } catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); else setImagesError(error instanceof AdminApiError && error.status === 409 ? "Оценка уже выполняется." : "Не удалось запустить оценку."); } finally { setEstimateSubmitting(false); }
  };
  useEffect(() => {
    if (images?.estimate_status !== "queued" && images?.estimate_status !== "running") return;
    const timer = window.setTimeout(() => {
      void api<ImageAnalysis>("/media/analysis").then(({ data }) => setImages(data)).catch(() => undefined);
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [images?.estimate_status]);
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
      <div className="admin-section-heading"><h2 className="admin-section-title">Ресурсы VPS</h2><button className="admin-icon-button" type="button" onClick={() => void refreshMetrics()} disabled={metricsRefreshing} aria-label="Обновить ресурсы VPS" title="Обновить"><RefreshCw className={metricsRefreshing ? "spinning" : ""} /></button></div>
      {metricsFailed && !metrics ? <p className="admin-muted">Данные временно недоступны. Нажмите обновить.</p> : !metrics ? <p className="admin-muted">Загружаем последний снимок VPS…</p> : <><div className="admin-resource-grid"><ResourceCard label="Диск" used={metrics.disk.used_bytes} total={metrics.disk.size_bytes} /><ResourceCard label="Оперативная память" used={metrics.memory.used_bytes} total={metrics.memory.total_bytes} /><article className="admin-resource-card"><p>CPU · load average</p><strong>{metrics.cpu.load_1.toFixed(2)}</strong><small>5 мин: {metrics.cpu.load_5.toFixed(2)} · 15 мин: {metrics.cpu.load_15.toFixed(2)}</small></article><article className="admin-resource-card"><p>Время работы</p><strong>{formatDuration(metrics.uptime_seconds)}</strong><small>обновлено {new Date(metrics.collected_at).toLocaleTimeString("ru-RU")}</small></article></div>{metricsFailed && <p className="admin-form-error" role="alert">Не удалось обновить данные VPS. Показан последний снимок.</p>}<div className="admin-table-wrap"><table><thead><tr><th>Контейнер</th><th>CPU</th><th>Память</th></tr></thead><tbody>{metrics.containers.map((container) => <tr key={container.name}><td>{container.name}</td><td>{container.cpu_percent.toFixed(2)}%</td><td>{container.memory_usage} / {container.memory_limit}</td></tr>)}</tbody></table></div></>}
      <div className="admin-section-heading"><h2 className="admin-section-title">Изображения</h2><button className="admin-icon-button" type="button" onClick={() => void refreshImages()} disabled={imagesRefreshing} aria-label="Собрать отчёт по изображениям" title="Собрать отчёт"><RefreshCw className={imagesRefreshing ? "spinning" : ""} /></button></div>
      {imagesLoading ? <p className="admin-muted">Загружаем последний отчёт…</p> : !images ? <p className="admin-muted">Отчёта ещё нет. Нажмите обновить: расчёт использует только агрегаты БД.</p> : <div className="admin-media-report"><p className="admin-muted">{images.file_count} файлов · {formatBytes(images.total_bytes)} · готовые: {images.permanent_file_count} / {formatBytes(images.permanent_bytes)} · временные: {images.temporary_file_count} / {formatBytes(images.temporary_bytes)}. По данным БД, {new Date(images.collected_at).toLocaleString("ru-RU")}.</p><p className="admin-muted">Форматы: {images.formats.map((item) => `${item.name}: ${item.file_count}`).join(", ") || "файлов пока нет"}.</p>{images.directories.length > 0 && <div className="admin-media-directories">{images.directories.map((item) => <span key={item.name}>{item.name === "other" ? "Остальное" : item.name}: {formatBytes(item.total_bytes)} ({item.percent ?? 0}%)</span>)}</div>}<div className="admin-media-actions"><button className="admin-table-action" type="button" disabled={estimateSubmitting || images.estimate_status === "queued" || images.estimate_status === "running"} onClick={() => void estimateImages()}>{estimateSubmitting || images.estimate_status === "queued" || images.estimate_status === "running" ? "Оцениваем…" : "Оценить экономию WebP"}</button>{images.estimate && <p className="admin-muted">Проба quality {images.estimate.quality}: {images.estimate.sample_file_count} файлов / {formatBytes(images.estimate.sample_bytes)}, экономия {images.estimate.sample_saved_percent}% (≈ {formatBytes(images.estimate.estimated_saved_bytes)} для всех подходящих файлов). Оригиналы не изменялись.</p>}</div></div>}
      {imagesError && <p className="admin-form-error" role="alert">{imagesError}</p>}
    </section>
  );
}

function ResourceCard({ label, used, total }: { label: string; used: number; total: number }) {
  const percent = total ? Math.round((used / total) * 100) : 0;
  return <article className="admin-resource-card"><p>{label}</p><strong>{percent}%</strong><small>{formatBytes(used)} из {formatBytes(total)}</small><i><b style={{ width: `${percent}%` }} /></i></article>;
}

const rejectionReasons = [
  ["unclear_description", "Непонятное или неполное описание"], ["prohibited_content", "Запрещённый контент"],
  ["paid_or_advertising", "Платное или рекламное событие"], ["inappropriate_photo", "Неподходящая фотография"],
  ["invalid_place_or_time", "Неверное место или время"], ["duplicate_or_spam", "Дубликат или спам"],
] as const;

function Moderation(props: { csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string>; onExpire: () => void }) {
  const requested = new URLSearchParams(window.location.search).get("queue") as ModerationQueue | null;
  const [queue, setQueueState] = useState<ModerationQueue>(requested && ["events", "reports", "appeals"].includes(requested) ? requested : "events");
  const [counts, setCounts] = useState<ModerationCounts>({ events: 0, reports: 0, appeals: 0 });
  const loadCounts = useCallback(async () => {
    try { setCounts((await api<ModerationCounts>("/moderation/counts")).data); }
    catch (error) { if (error instanceof AdminApiError && error.status === 401) props.onExpire(); }
  }, [props.onExpire]);
  useEffect(() => { void loadCounts(); }, [loadCounts]);
  const setQueue = (next: ModerationQueue) => {
    setQueueState(next);
    const url = new URL(window.location.href);
    url.searchParams.set("view", "moderation");
    url.searchParams.set("queue", next);
    window.history.replaceState(null, "", url);
  };
  return <section className="admin-moderation"><header className="admin-page-header"><div><p>Очереди безопасности и качества</p><h1>Модерация</h1></div></header><div className="admin-tabs" role="tablist" aria-label="Очереди модерации">{(["events", "reports", "appeals"] as const).map((item) => <button key={item} type="button" role="tab" aria-selected={queue === item} className={queue === item ? "active" : ""} onClick={() => setQueue(item)}>{item === "events" ? <ClipboardCheck /> : item === "reports" ? <Flag /> : <Gavel />}<span>{item === "events" ? "События" : item === "reports" ? "Жалобы" : "Апелляции"}</span><b>{counts[item]}</b></button>)}</div>{queue === "events" ? <EventModeration {...props} onChanged={loadCounts} /> : <CaseModerationV2 queue={queue} {...props} onChanged={loadCounts} />}</section>;
}

function EventModeration({ csrf, onCsrf, renewCsrf, onExpire, onChanged }: { csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string>; onExpire: () => void; onChanged: () => Promise<void> }) {
  const [items, setItems] = useState<Review[] | null>(null);
  const [selected, setSelected] = useState<ReviewDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<"approve" | "reject" | "open" | null>(null);
  const [reason, setReason] = useState<(typeof rejectionReasons)[number][0]>("unclear_description");
  const [decisionError, setDecisionError] = useState("");
  const [decisionMessage, setDecisionMessage] = useState("");
  const [anchors, setAnchors] = useState<StreetAnchor[]>([]);
  const [anchorId, setAnchorId] = useState("");
  const [newAnchor, setNewAnchor] = useState(false);
  const [anchorName, setAnchorName] = useState("");
  const [anchorLatitude, setAnchorLatitude] = useState("");
  const [anchorLongitude, setAnchorLongitude] = useState("");
  const load = useCallback(async () => {
    try {
      const result = await api<{ items: Review[] }>("/events/reviews");
      onCsrf(result.response.headers.get(csrfHeader) ?? ""); setItems(result.data.items); setFailed(false);
    } catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); else { setFailed(true); setItems([]); } }
  }, [onCsrf, onExpire]);
  useEffect(() => { void load(); }, [load]);
  const open = async (review: Review) => {
    setBusy("open");
    try { const result = await api<ReviewDetail>(`/events/reviews/${review.id}`); onCsrf(result.response.headers.get(csrfHeader) ?? ""); setSelected(result.data); setAnchorId(result.data.street_anchor_id ?? ""); setAnchorName(result.data.organizer_street ?? ""); setAnchorLatitude(String(result.data.latitude)); setAnchorLongitude(String(result.data.longitude)); setNewAnchor(false); if (result.data.address_visibility !== "exact_public") { const catalog = await fetch("/api/geo/catalog").then((response) => response.json() as Promise<{ cities: CityOption[] }>); const city = catalog.cities.find((item) => item.name === result.data.city); if (city) { const list = await api<{ items: StreetAnchor[] }>(`/street-anchors?city_id=${city.id}&limit=100`); setAnchors(list.data.items); } } }
    catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); }
    finally { setBusy(null); }
  };
  const decide = async (action: "approve" | "reject") => {
    if (!selected) return;
    setBusy(action); setDecisionError("");
    const isPrivate = selected.address_visibility !== "exact_public";
    if (action === "approve" && isPrivate && !anchorId && !newAnchor) { setDecisionError("Для закрытого адреса выберите существующую улицу или создайте примерную точку."); return; }
    if (action === "approve" && newAnchor && (!anchorName.trim() || !anchorLatitude || !anchorLongitude)) { setDecisionError("Укажите название улицы и примерные координаты точки."); return; }
    const request = async (token: string) => await api(`/events/reviews/${selected.id}/${action}`, { method: "POST", headers: { "Content-Type": "application/json", [csrfHeader]: token }, body: JSON.stringify({ revision_id: selected.event_revision_id, reason: action === "reject" ? reason : null, street_anchor_id: action === "approve" && !newAnchor ? anchorId || null : null, new_street_anchor: action === "approve" && newAnchor ? { display_name: anchorName, latitude: Number(anchorLatitude), longitude: Number(anchorLongitude) } : null }) });
    try {
      let result: { data: undefined; response: Response };
      try { result = await request(csrf); }
      catch (error) { if (!(error instanceof AdminApiError) || error.status !== 401) throw error; result = await request(await renewCsrf()); }
      onCsrf(result.response.headers.get(csrfHeader) ?? ""); setSelected(null); await load(); await onChanged();
      setDecisionMessage(action === "approve" ? "Событие одобрено и опубликовано." : "Событие отклонено, автор получит причину.");
    } catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); else setDecisionError(moderationErrorMessage(error)); }
    finally { setBusy(null); }
  };
  return <section className="admin-queue-panel">{decisionMessage && <p className="success-message" role="status">{decisionMessage}</p>}
    {failed ? <AdminEmpty title="Очередь недоступна" text="Обновите страницу и попробуйте снова." /> : items === null ? <AdminStatus text="Загружаем очередь…" /> : !items.length ? <AdminEmpty title="Очередь пуста" text="Новых событий на проверке нет." /> : <div className="admin-table-wrap"><table><thead><tr><th>Событие</th><th>Автор</th><th>Город</th><th>Начало</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.title}</td><td>{item.display_name}</td><td>{item.city}</td><td>{new Date(item.starts_at).toLocaleString("ru-RU")}</td><td><button className="admin-table-action" disabled={busy !== null} onClick={() => void open(item)}>Проверить</button></td></tr>)}</tbody></table></div>}
    {selected && <div className="admin-modal-backdrop" role="presentation"><section className="admin-review" role="dialog" aria-modal="true" aria-label="Проверка события"><button className="admin-close" onClick={() => setSelected(null)} aria-label="Закрыть">×</button><p>Событие от {selected.display_name} · ID {selected.public_id}</p><h2>{selected.title}</h2><img src={selected.photo_url} alt="Фото события" /><dl><div><dt>Категория</dt><dd>{selected.category}</dd></div><div><dt>Город</dt><dd>{selected.city}</dd></div><div><dt>Время</dt><dd>{new Date(selected.starts_at).toLocaleString("ru-RU")} — {new Date(selected.ends_at).toLocaleString("ru-RU")}</dd></div><div><dt>Адрес карты</dt><dd>{selected.normalized_address}</dd></div>{selected.organizer_street && <div><dt>Улица организатора</dt><dd>{selected.organizer_street}</dd></div>}{selected.organizer_place && <div><dt>Дом, место или ориентир</dt><dd>{selected.organizer_place}</dd></div>}{selected.organizer_address && <div><dt>Адрес для карточки</dt><dd>{selected.organizer_address}</dd></div>}<div><dt>Видимость</dt><dd>{visibilityLabel(selected.address_visibility)}</dd></div><div><dt>Лимит</dt><dd>{selected.capacity ?? "Без ограничения"}</dd></div></dl><h3>Описание</h3><p className="admin-review-description">{selected.description}</p>{selected.address_visibility !== "exact_public" && <fieldset className="admin-anchor-choice"><legend>Общая метка улицы</legend><p className="admin-muted">Точная точка события видна только модераторам. Публичной станет приблизительная точка улицы.</p><label><input type="radio" checked={!newAnchor} onChange={() => setNewAnchor(false)} /> Выбрать существующую</label><select value={anchorId} disabled={newAnchor} onChange={(event) => setAnchorId(event.target.value)}><option value="">Выберите улицу</option>{anchors.map((anchor) => <option value={anchor.id} key={anchor.id}>{anchor.display_name} · {anchor.active_event_count} активных</option>)}</select><label><input type="radio" checked={newAnchor} onChange={() => setNewAnchor(true)} /> Создать новую</label>{newAnchor && <div className="admin-anchor-fields"><label>Название улицы<input value={anchorName} maxLength={200} onChange={(event) => setAnchorName(event.target.value)} /></label><label>Широта примерной точки<input value={anchorLatitude} inputMode="decimal" onChange={(event) => setAnchorLatitude(event.target.value)} /></label><label>Долгота примерной точки<input value={anchorLongitude} inputMode="decimal" onChange={(event) => setAnchorLongitude(event.target.value)} /></label><small>Поставьте приблизительную точку улицы; она не должна совпадать с точным местом события.</small></div>}</fieldset>}{decisionError && <p className="admin-form-error" role="alert">{decisionError}</p>}<div className="admin-review-actions"><button className="admin-approve" disabled={busy !== null} onClick={() => void decide("approve")}>{busy === "approve" ? "Одобряем…" : "Одобрить"}</button><div className="admin-reject-group"><select value={reason} disabled={busy !== null} onChange={(event) => setReason(event.target.value as typeof reason)} aria-label="Причина отклонения">{rejectionReasons.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><button className="admin-reject" disabled={busy !== null} onClick={() => void decide("reject")}>{busy === "reject" ? "Отклоняем…" : "Отклонить"}</button></div></div></section></div>}
  </section>;
}


function CaseModerationV2({ queue, csrf, onCsrf, renewCsrf, onExpire, onChanged }: { queue: "reports" | "appeals"; csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string>; onExpire: () => void; onChanged: () => Promise<void> }) {
  const [items, setItems] = useState<ModerationCase[] | null>(null);
  const [selected, setSelected] = useState<ModerationCaseDetail | null>(null);
  const [typeFilter, setTypeFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [confirmAction, setConfirmAction] = useState<CaseAction | null>(null);
  const [decisionKey, setDecisionKey] = useState<string | null>(null);
  const load = useCallback(async () => {
    setItems(null); setError("");
    try { setItems((await api<{ items: ModerationCase[] }>(`/moderation/cases?queue=${queue}&status=open`)).data.items); }
    catch (reason) { if (reason instanceof AdminApiError && reason.status === 401) onExpire(); else { setItems([]); setError("Очередь недоступна. Повторите загрузку."); } }
  }, [onExpire, queue]);
  useEffect(() => { void load(); setSelected(null); }, [load]);
  const setCaseInUrl = (value: string | null) => {
    const url = new URL(window.location.href);
    if (value) url.searchParams.set("case", value); else url.searchParams.delete("case");
    window.history.replaceState(null, "", url);
  };
  const open = useCallback(async (publicId: string) => {
    setError(""); setNote(""); setDecisionKey(null);
    try { setSelected((await api<ModerationCaseDetail>(`/moderation/cases/${publicId}`)).data); setCaseInUrl(publicId); }
    catch { setError("Не удалось открыть обращение."); }
  }, []);
  useEffect(() => {
    if (items === null || selected) return;
    const requested = new URLSearchParams(window.location.search).get("case");
    if (requested && items.some((item) => item.public_id === requested)) void open(requested);
  }, [items, open, selected]);
  const close = () => { if (!busy) { setSelected(null); setConfirmAction(null); setCaseInUrl(null); } };
  const submit = async (decision: CaseAction) => {
    if (!selected || !note.trim()) { setError("Добавьте внутреннее обоснование решения."); return; }
    setBusy(true); setError("");
    const endpoint = queue === "appeals" ? "appeal-decision" : "decision";
    const payload = queue === "appeals"
      ? { decision, staff_note: note.trim(), expected_version: selected.version }
      : { decision, subject_component: selected.target.component, staff_note: note.trim(), expected_version: selected.version };
    const key = decisionKey ?? crypto.randomUUID();
    if (!decisionKey) setDecisionKey(key);
    const request = async (token: string) => api(`/moderation/cases/${selected.public_id}/${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json", [csrfHeader]: token, "Idempotency-Key": key }, body: JSON.stringify(payload) });
    try {
      let result;
      try { result = await request(csrf); } catch (reason) { if (!(reason instanceof AdminApiError) || reason.status !== 401) throw reason; result = await request(await renewCsrf()); }
      onCsrf(result.response.headers.get(csrfHeader) ?? "");
      setSelected(null);
      setConfirmAction(null);
      setDecisionKey(null);
      setCaseInUrl(null);
      setSuccess(`Решение по ${selected.public_id} сохранено: ${actionResultLabel(decision, selected)}.`);
      await Promise.all([load(), onChanged()]);
    } catch (reason) {
      if (reason instanceof AdminApiError && reason.detail === "case_evidence_stale") setError("Контент изменился после жалобы. Обновите очередь и проверьте актуальную версию.");
      else if (reason instanceof AdminApiError && reason.detail === "subject_action_conflict") setError("Цель уже удалена или изменилась. Обновите очередь перед повторным решением.");
      else if (reason instanceof AdminApiError && reason.status === 409) setError("Обращение уже изменилось. Обновите очередь.");
      else setError("Сервер не сохранил решение. Проверьте соединение и повторите попытку.");
    } finally { setBusy(false); setConfirmAction(null); }
  };
  const filtered = (items ?? []).filter((item) => (typeFilter === "all" || item.subject_type === typeFilter) && (priorityFilter === "all" || item.priority === priorityFilter));
  return <section className="admin-queue-panel">
    <p className="admin-sr-status" role="status" aria-live="polite">{success}</p>
    <div className="admin-filters"><label>Объект<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">Все</option><option value="event">События</option><option value="profile">Профили</option><option value="looking_post">Идеи</option><option value="q_and_a_answer">Ответы</option><option value="chat_message">Сообщения чата</option></select></label><label>Приоритет<select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}><option value="all">Любой</option><option value="critical">Критический</option><option value="high">Высокий</option><option value="normal">Обычный</option></select></label><button className="admin-table-action" type="button" onClick={() => void load()}>Обновить</button></div>
    {error && !selected && <p className="admin-form-error admin-queue-error" role="alert">{error}</p>}
    {items === null ? <AdminStatus text="Загружаем очередь…" /> : !filtered.length ? <AdminEmpty title="Очередь пуста" text={queue === "reports" ? "Новых жалоб нет." : "Апелляций на рассмотрении нет."} /> : <><div className="admin-table-wrap admin-case-table"><table><thead><tr><th>Номер</th><th>Цель</th><th>Объект</th><th>Причина</th><th>Приоритет</th><th /></tr></thead><tbody>{filtered.map((item) => <tr key={item.public_id}><td><strong>{item.public_id}</strong></td><td><strong>{targetLabel(item.subject_type, item.subject_component)}</strong></td><td>{item.target_title ?? "Удалённый объект"}</td><td>{reasonLabel(item.reason_code)}</td><td><span className={`admin-priority ${item.priority}`}>{priorityLabel(item.priority)}</span></td><td><Button variant="outline" size="sm" onClick={() => void open(item.public_id)}>Открыть</Button></td></tr>)}</tbody></table></div><div className="admin-case-cards">{filtered.map((item) => <article key={item.public_id}><header><strong>{targetLabel(item.subject_type, item.subject_component)}</strong><span className={`admin-priority ${item.priority}`}>{priorityLabel(item.priority)}</span></header><h3>{item.target_title ?? "Удалённый объект"}</h3><p>{reasonLabel(item.reason_code)}</p><footer><small>{item.public_id}</small><Button variant="outline" size="sm" onClick={() => void open(item.public_id)}>Открыть</Button></footer></article>)}</div></>}
    <Sheet open={Boolean(selected)} onOpenChange={(openState) => { if (!openState) close(); }}><SheetContent className="admin-case-drawer" onEscapeKeyDown={(event) => { if (busy) event.preventDefault(); }} onPointerDownOutside={(event) => { if (busy) event.preventDefault(); }}>{selected && <><p className="admin-kicker">Жалоба на: {componentTargetLabel(selected.target.subject_type, selected.target.component)}</p><SheetTitle id="case-title">{selected.target.title || selected.public_id}</SheetTitle><SheetDescription>{selected.target.owner_name ? `Автор: ${selected.target.owner_name} · ` : ""}{selected.public_id}</SheetDescription><dl><div><dt>Причина</dt><dd>{reasonLabel(selected.reason_code)}</dd></div><div><dt>Приоритет</dt><dd>{priorityLabel(selected.priority)}</dd></div><div><dt>Ожидает с</dt><dd>{new Date(selected.created_at).toLocaleString("ru-RU")}</dd></div></dl>{selected.explanation && <section><h3>Пояснение пользователя</h3><blockquote className="admin-case-text">{selected.explanation}</blockquote></section>}<section><h3>Зафиксированное доказательство</h3>{selected.evidence_state === "changed" && <p className="admin-evidence-warning" role="alert">Контент изменился после отправки жалобы. Подтверждающие действия заблокированы сервером.</p>}<CaseEvidence detail={selected} /></section>{selected.appeal && <section><h3>Апелляция</h3><p className="admin-case-text">{selected.appeal.explanation}</p></section>}<details className="admin-case-secondary"><summary>История и предыдущие решения</summary><ol className="admin-case-timeline">{selected.timeline.map((entry) => <li key={`${entry.event_type}-${entry.created_at}`}><span /><div><strong>{entry.public_label}</strong><small>{new Date(entry.created_at).toLocaleString("ru-RU")}</small></div></li>)}</ol>{selected.decisions.map((decision) => <p className="admin-case-text" key={`${decision.decision_type}-${decision.created_at}`}><strong>{decision.actor}: {decisionLabel(decision.decision_type)}</strong><br />{decision.staff_note}</p>)}</details><label className="admin-case-note" htmlFor="case-note">Внутренняя заметка<textarea id="case-note" maxLength={1000} value={note} aria-invalid={Boolean(error && !note.trim())} aria-describedby="case-note-help case-note-error" onChange={(event) => { setNote(event.target.value); if (error && event.target.value.trim()) setError(""); }} placeholder="Кратко зафиксируйте факты и основание решения" /><small id="case-note-help">Обязательное обоснование для аудита. Пользователь его не увидит.</small></label>{error && <p id="case-note-error" className="admin-form-error" role="alert">{error}</p>}<div className="admin-case-actions">{(queue === "appeals" ? ["reversed", "upheld"] as CaseAction[] : selected.available_actions).map((action) => <Button key={action} variant={action === "dismiss" || action === "reversed" ? "outline" : action === "upheld" ? "default" : "destructive"} disabled={busy || !note.trim() || (selected.evidence_state === "changed" && action !== "dismiss")} onClick={() => action === "dismiss" ? void submit(action) : setConfirmAction(action)}>{actionButtonLabel(action, selected)}</Button>)}</div></>}</SheetContent></Sheet>
    <AlertDialog open={Boolean(confirmAction)} onOpenChange={(openState) => { if (!openState && !busy) setConfirmAction(null); }} title={confirmAction && selected ? `${actionButtonLabel(confirmAction, selected)}?` : "Подтвердите решение"} description={confirmAction && selected ? actionConsequence(confirmAction, selected) : ""} confirmLabel="Применить" busyLabel="Сохраняем…" busy={busy} onConfirm={() => { if (confirmAction) void submit(confirmAction); }} />
  </section>;
}

function CaseEvidence({ detail }: { detail: ModerationCaseDetail }) {
  const value = detail.evidence.value || "Содержимое отсутствовало";
  if (["photo", "avatar", "background"].includes(detail.target.component)) {
    const src = detail.evidence.value ? `/api/admin/moderation/evidence/${detail.public_id}` : "";
    return <figure className="admin-evidence-card media">{src ? <img src={src} alt={`Доказательство: ${componentLabel(detail.target.component)}`} /> : <div className="admin-evidence-empty">Изображение отсутствовало при отправке жалобы</div>}<figcaption><strong>{componentLabel(detail.target.component)}</strong><small>Снимок зафиксирован {new Date(detail.evidence.captured_at).toLocaleString("ru-RU")}</small></figcaption></figure>;
  }
  return <blockquote className={`admin-evidence-card ${detail.target.subject_type === "chat_message" ? "message" : "text"}`}><span>{value}</span><footer>{detail.evidence.context_title && <strong>{detail.evidence.context_title}</strong>}<small>Зафиксировано {new Date(detail.evidence.captured_at).toLocaleString("ru-RU")}</small></footer></blockquote>;
}

export function targetLabel(subject: string, component: string | null) { const labels: Record<string, Record<string, string>> = { event: { photo: "Фотография события", title: "Название события", description: "Описание события", schedule: "Дата и время события", location: "Место события", whole: "Событие целиком" }, profile: { avatar: "Аватар профиля", background: "Фон профиля", display_name: "Имя профиля", bio: "Описание профиля", whole: "Профиль целиком" }, looking_post: { title: "Название идеи", body: "Описание идеи", whole: "Идея целиком" }, q_and_a_answer: { answer: "Текст ответа в Q&A" }, chat_message: { message: "Сообщение чата" } }; return labels[subject]?.[component ?? ""] ?? "Неизвестная цель"; }
function componentTargetLabel(subject: string, component: string) { return targetLabel(subject, component).toLocaleLowerCase("ru-RU"); }
function actionButtonLabel(action: CaseAction, detail: ModerationCaseDetail) { const shortComponent: Record<string, string> = { photo: "фотографию", avatar: "аватар", background: "фон", display_name: "имя", bio: "описание", title: "название", body: "описание", answer: "ответ", message: "сообщение" }; return ({ dismiss: "Отклонить", hide_component: `Скрыть ${shortComponent[detail.target.component] ?? "компонент"}`, hold_for_correction: "Снять до исправления", hide_subject: "Скрыть полностью", upheld: "Оставить в силе", reversed: "Отменить решение" } as Record<CaseAction, string>)[action]; }
function actionConsequence(action: CaseAction, _detail: ModerationCaseDetail) { if (action === "hide_component") return "Выбранный компонент будет скрыт. Решение можно будет обжаловать."; if (action === "hold_for_correction") return "Объект будет скрыт до исправления и повторной проверки."; if (action === "hide_subject") return "Объект будет скрыт целиком. Решение можно будет обжаловать."; return "Решение будет записано в историю модерации."; }
function actionResultLabel(action: CaseAction, _detail: ModerationCaseDetail) { if (action === "dismiss") return "жалоба отклонена"; if (action === "hide_component") return "выбранный компонент скрыт"; if (action === "hold_for_correction") return "объект снят до исправления"; if (action === "hide_subject") return "объект скрыт полностью"; return "решение по апелляции сохранено"; }
function decisionLabel(value: string) { return ({ dismiss: "Жалоба отклонена", hide_component: "Компонент скрыт", hold_for_correction: "Снято до исправления", hide_subject: "Объект скрыт", appeal_upheld: "Решение оставлено в силе", appeal_reversed: "Решение отменено" } as Record<string, string>)[value] ?? value; }

function subjectLabel(value: string) { return ({ event: "Событие", profile: "Профиль", looking_post: "Идея", q_and_a_answer: "Ответ в Q&A", chat_message: "Сообщение чата" } as Record<string, string>)[value] ?? "Неизвестная цель"; }
function componentLabel(value: string | null) { return ({ photo: "Фото", title: "Название", description: "Описание", schedule: "Дата и время", location: "Место", whole: "Весь объект", avatar: "Аватар", background: "Фон", bio: "Описание", display_name: "Имя", body: "Текст", answer: "Ответ", message: "Сообщение" } as Record<string, string>)[value ?? ""] ?? "Неизвестная часть"; }
function priorityLabel(value: string) { return ({ critical: "Критический", high: "Высокий", normal: "Обычный" } as Record<string, string>)[value] ?? value; }
function reasonLabel(value: string | null) { return ({ photo: "Фотография", display_name: "Имя", bio: "Описание", safety_risk: "Угроза безопасности", misleading: "Вводящие в заблуждение данные", spam_or_commerce: "Спам или коммерция", inappropriate_content: "Недопустимый контент", other: "Другое" } as Record<string, string>)[value ?? ""] ?? value ?? "Не указана"; }

function Streets({ csrf, onExpire }: { csrf: string; onExpire: () => void }) {
  const [cities, setCities] = useState<CityOption[]>([]); const [cityId, setCityId] = useState("");
  const [query, setQuery] = useState(""); const [items, setItems] = useState<StreetAnchor[] | null>(null);
  const [error, setError] = useState(""); const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ display_name: "", latitude: "", longitude: "" });
  const load = useCallback(async (targetCity = cityId) => { if (!targetCity) return; try { const result = await api<{ items: StreetAnchor[] }>(`/street-anchors?city_id=${targetCity}&q=${encodeURIComponent(query)}`); setItems(result.data.items); setError(""); } catch (reason) { if (reason instanceof AdminApiError && reason.status === 401) onExpire(); else setError("Не удалось загрузить улицы."); } }, [cityId, onExpire, query]);
  useEffect(() => { void fetch("/api/geo/catalog").then((response) => response.json() as Promise<{ cities: CityOption[] }>).then((data) => { setCities(data.cities); setCityId(data.cities[0]?.id ?? ""); }).catch(() => setError("Не удалось загрузить города.")); }, []);
  useEffect(() => { void load(); }, [load]);
  const create = async (event: FormEvent) => { event.preventDefault(); setError(""); try { await api("/street-anchors", { method: "POST", headers: { "Content-Type": "application/json", [csrfHeader]: csrf }, body: JSON.stringify({ city_id: cityId, display_name: form.display_name, latitude: Number(form.latitude), longitude: Number(form.longitude) }) }); setCreating(false); setForm({ display_name: "", latitude: "", longitude: "" }); await load(); } catch (reason) { setError(reason instanceof AdminApiError && reason.detail === "street_anchor_exists" ? "Такая улица уже есть: выберите её из списка." : "Не удалось сохранить улицу. Проверьте точку и повторите."); } };
  return <section><header className="admin-page-header"><div><p>Приблизительные общие точки</p><h1>Улицы</h1></div><button className="admin-table-action" onClick={() => setCreating((value) => !value)}>Добавить улицу</button></header><div className="admin-filters"><label>Город<select value={cityId} onChange={(event) => setCityId(event.target.value)}>{cities.map((city) => <option value={city.id} key={city.id}>{city.name}</option>)}</select></label><label>Поиск<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название улицы" /></label><button className="admin-table-action" onClick={() => void load()}>Найти</button></div>{creating && <form className="admin-anchor-form" onSubmit={create}><h2>Новая общая точка</h2><p className="admin-muted">Укажите единое название и приблизительную точку улицы. Точные координаты событий сюда не копируются.</p><label>Название улицы<input value={form.display_name} maxLength={200} required onChange={(event) => setForm({ ...form, display_name: event.target.value })} /></label><label>Широта<input value={form.latitude} inputMode="decimal" required onChange={(event) => setForm({ ...form, latitude: event.target.value })} /></label><label>Долгота<input value={form.longitude} inputMode="decimal" required onChange={(event) => setForm({ ...form, longitude: event.target.value })} /></label><button type="submit">Сохранить улицу</button></form>}{error && <p className="admin-form-error" role="alert">{error}</p>}{items === null ? <AdminStatus text="Загружаем улицы…" /> : !items.length ? <AdminEmpty title="Улиц пока нет" text="Их можно создать заранее или прямо при модерации закрытого адреса." /> : <div className="admin-table-wrap"><table><thead><tr><th>Улица</th><th>Активные события</th><th>Источник</th><th>Изменено</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.display_name}</td><td>{item.active_event_count}</td><td>{item.source === "staff" ? "Модератор" : "Nominatim"}</td><td>{new Date(item.updated_at).toLocaleString("ru-RU")}</td></tr>)}</tbody></table></div>}</section>;
}

function Audit({ onCsrf, onExpire }: { csrf: string; onCsrf: (value: string) => void; onExpire: () => void }) {
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
    } catch (error) { if (error instanceof AdminApiError && error.status === 401) onExpire(); else setFailed(true); } finally { setBusy(false); }
  }, [onCsrf, onExpire]);
  useEffect(() => { void load(); }, [load]);
  return (
    <section>
      <header className="admin-page-header"><div><p>Безопасность</p><h1>История действий</h1></div></header>
      {failed && !items.length ? <AdminEmpty title="История недоступна" text="Обновите страницу и попробуйте снова." /> : !busy && !items.length ? <AdminEmpty title="Действий пока нет" text="Здесь появятся входы и административные изменения." /> : <div className="admin-table-wrap"><table><thead><tr><th>Время</th><th>Администратор</th><th>Действие</th><th>Результат</th></tr></thead><tbody>{items.map((entry) => <tr key={entry.id}><td>{new Date(entry.created_at).toLocaleString("ru-RU")}</td><td>{entry.actor ?? "Система"}</td><td>{actionLabel(entry.action)}</td><td><span className={`admin-result ${entry.result}`}>{resultLabel(entry.result)}</span></td></tr>)}</tbody></table>{next && <button className="admin-more" disabled={busy} onClick={() => void load(next)}>{busy ? "Загружаем…" : "Показать ещё"}</button>}</div>}
    </section>
  );
}

function AdminStatus({ text }: { text: string }) { return <main className="admin-status" role="status"><span /><p>{text}</p></main>; }
function AdminFullScreenStatus({ text }: { text: string }) { return <main className="admin-status" role="status" aria-live="polite"><span /><p>{text}</p></main>; }
function AdminEmpty({ title, text }: { title: string; text: string }) { return <div className="admin-empty"><History /><h2>{title}</h2><p>{text}</p></div>; }
function actionLabel(action: string) { return ({ "staff.bootstrap": "Создан первый администратор", "staff.login_bootstrap": "Подготовлен вход", "staff.login": "Вход в панель", "staff.logout": "Выход из панели" } as Record<string, string>)[action] ?? action; }
function resultLabel(result: AuditEntry["result"]) { return result === "success" ? "Успешно" : result === "blocked" ? "Заблокировано" : "Отказ"; }
function formatBytes(value: number) { if (value < 1024 * 1024) return `${Math.round(value / 1024)} КБ`; if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} МБ`; return `${(value / 1024 / 1024 / 1024).toFixed(1)} ГБ`; }
function formatDuration(value: number) { const days = Math.floor(value / 86400); const hours = Math.floor((value % 86400) / 3600); return days ? `${days} д. ${hours} ч.` : `${hours} ч.`; }

function visibilityLabel(value: string) { return ({ exact_public: "Точный адрес виден всем", exact_participants: "Точный адрес виден участникам", street_only: "Публично видна только улица" } as Record<string, string>)[value] ?? value; }
function moderationErrorMessage(error: unknown) { if (!(error instanceof AdminApiError)) return "Не удалось сохранить решение. Попробуйте ещё раз."; if (error.status === 409) return "Заявка уже обработана или изменилась. Обновите очередь."; if (error.status === 422 && error.detail === "event_already_started") return "Нельзя одобрить событие, которое уже началось."; return "Не удалось сохранить решение. Попробуйте ещё раз."; }
class AdminApiError extends Error { constructor(public status: number, public detail?: string) { super("Admin request failed"); } }
async function api<T = undefined>(path: string, init?: RequestInit): Promise<{ data: T; response: Response }> {
  const response = await fetch(`/api/admin${path}`, { ...init, credentials: "same-origin", headers: { Accept: "application/json", ...init?.headers } });
  if (!response.ok) { const body = await response.json().catch(() => null) as { detail?: string } | null; throw new AdminApiError(response.status, body?.detail); }
  const data = response.status === 204 ? undefined : await response.json();
  return { data: data as T, response };
}
