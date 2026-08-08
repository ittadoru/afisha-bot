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
type View = "dashboard" | "moderation" | "special" | "audit";
type SpecialEvent = { id: string; title: string; starts_at: string; ends_at: string; city: string };
type CityOption = { id: string; slug: string; name: string; center_latitude: number; center_longitude: number };
type Review = { id: string; event_id: string; event_revision_id: string; submitted_at: string; title: string; starts_at: string; city: string; public_id: string; display_name: string };
type ReviewDetail = Review & { description: string; ends_at: string; normalized_address: string; street_name: string | null; landmark: string | null; address_visibility: string; latitude: number; longitude: number; capacity: number | null; category: string; organizer_status: string; successful_events: number; photo_url: string };
type SystemMetrics = { collected_at: string; disk: { size_bytes: number; used_bytes: number; available_bytes: number }; memory: { total_bytes: number; used_bytes: number; available_bytes: number }; cpu: { load_1: number; load_5: number; load_15: number }; uptime_seconds: number; containers: Array<{ name: string; cpu_percent: number; memory_usage: string; memory_limit: string }> };
type ImageAnalysis = { file_count: number; total_bytes: number; formats: Record<string, number> };

const csrfHeader = "X-Afisha-Admin-CSRF";

export function AdminApp() {
  const [staff, setStaff] = useState<Staff | null>(null);
  const [csrf, setCsrf] = useState("");
  const [checking, setChecking] = useState(true);
  const adoptCsrf = useCallback((token: string) => { if (token) setCsrf(token); }, []);
  const renewCsrf = useCallback(async () => {
    const result = await api<Staff>("/account/me");
    const token = result.response.headers.get(csrfHeader);
    if (!token) throw new AdminApiError(401);
    setStaff(result.data);
    setCsrf(token);
    return token;
  }, []);

  useEffect(() => {
    void api<Staff>("/account/me").then(({ data, response }) => {
      setStaff(data);
      adoptCsrf(response.headers.get(csrfHeader) ?? "");
    }).catch(() => undefined).finally(() => setChecking(false));
  }, []);

  if (checking) return <AdminStatus text="Проверяем доступ…" />;
  if (!staff) {
    return <AdminLogin onLogin={(account, token) => { setStaff(account); setCsrf(token); }} />;
  }
  return <AdminShell staff={staff} csrf={csrf} onCsrf={adoptCsrf} renewCsrf={renewCsrf} onLogout={() => setStaff(null)} />;
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

function AdminShell({ staff, csrf, onCsrf, renewCsrf, onLogout }: { staff: Staff; csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string>; onLogout: () => void }) {
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
          <button className={view === "moderation" ? "active" : ""} onClick={() => setView("moderation")}><ClipboardCheck />Модерация</button>
          <button className={view === "special" ? "active" : ""} onClick={() => setView("special")}><Sparkles />Особые события</button>
          <button className={view === "audit" ? "active" : ""} onClick={() => setView("audit")}><History />История действий</button>
        </nav>
        <div className="admin-sidebar-footer">
          <div className="admin-person"><span>{staff.login.slice(0, 1).toUpperCase()}</span><div><strong>{staff.login}</strong><small>Администратор</small></div></div>
          <button onClick={() => void logout()}><LogOut />Выйти</button>
        </div>
      </aside>
      <main className="admin-content">
        {view === "dashboard" ? <Dashboard csrf={csrf} onCsrf={onCsrf} renewCsrf={renewCsrf} staff={staff} /> : view === "moderation" ? <Moderation csrf={csrf} onCsrf={onCsrf} renewCsrf={renewCsrf} /> : view === "special" ? <SpecialEvents csrf={csrf} onCsrf={onCsrf} /> : <Audit csrf={csrf} onCsrf={onCsrf} />}
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

function Dashboard({ staff, csrf, onCsrf, renewCsrf }: { csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string>; staff: Staff }) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [failed, setFailed] = useState(false);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [metricsFailed, setMetricsFailed] = useState(false);
  const [metricsRefreshing, setMetricsRefreshing] = useState(false);
  const [images, setImages] = useState<ImageAnalysis | null>(null);
  useEffect(() => {
    void api<Counts>("/dashboard").then(({ data, response }) => {
      setCounts(data); onCsrf(response.headers.get(csrfHeader) ?? "");
    }).catch(() => setFailed(true));
  }, [onCsrf]);
  const loadMetrics = useCallback(async () => {
    try { const result = await api<SystemMetrics>("/system/metrics"); setMetrics(result.data); onCsrf(result.response.headers.get(csrfHeader) ?? ""); setMetricsFailed(false); }
    catch { setMetricsFailed(true); }
  }, [onCsrf]);
  const refreshMetrics = async () => {
    setMetricsRefreshing(true); setMetricsFailed(false);
    const request = async (token: string) => await api<SystemMetrics>("/system/metrics/refresh", { method: "POST", headers: { [csrfHeader]: token } });
    try {
      let result: { data: SystemMetrics; response: Response };
      try { result = await request(csrf); }
      catch (error) { if (!(error instanceof AdminApiError) || error.status !== 401) throw error; result = await request(await renewCsrf()); }
      setMetrics(result.data); onCsrf(result.response.headers.get(csrfHeader) ?? "");
    } catch { setMetricsFailed(true); } finally { setMetricsRefreshing(false); }
  };
  useEffect(() => {
    void loadMetrics();
    void api<ImageAnalysis>("/media/analysis").then(({ data, response }) => { setImages(data); onCsrf(response.headers.get(csrfHeader) ?? ""); }).catch(() => undefined);
  }, [loadMetrics, onCsrf]);
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
      <h2 className="admin-section-title">Изображения</h2>
      {images ? <p className="admin-muted">{images.file_count} файлов · {formatBytes(images.total_bytes)} · {Object.entries(images.formats).map(([format, count]) => `${format}: ${count}`).join(", ") || "файлов пока нет"}. Повторное сжатие не выполнялось.</p> : <p className="admin-muted">Анализируем файлы…</p>}
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

function Moderation({ csrf, onCsrf, renewCsrf }: { csrf: string; onCsrf: (value: string) => void; renewCsrf: () => Promise<string> }) {
  const [items, setItems] = useState<Review[] | null>(null);
  const [selected, setSelected] = useState<ReviewDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState<(typeof rejectionReasons)[number][0]>("unclear_description");
  const [decisionError, setDecisionError] = useState("");
  const [decisionMessage, setDecisionMessage] = useState("");
  const load = useCallback(async () => {
    try {
      const result = await api<{ items: Review[] }>("/events/reviews");
      onCsrf(result.response.headers.get(csrfHeader) ?? ""); setItems(result.data.items); setFailed(false);
    } catch { setFailed(true); setItems([]); }
  }, [onCsrf]);
  useEffect(() => { void load(); }, [load]);
  const open = async (review: Review) => {
    setBusy(true);
    try { const result = await api<ReviewDetail>(`/events/reviews/${review.id}`); onCsrf(result.response.headers.get(csrfHeader) ?? ""); setSelected(result.data); }
    finally { setBusy(false); }
  };
  const decide = async (action: "approve" | "reject") => {
    if (!selected) return;
    setBusy(true); setDecisionError("");
    const request = async (token: string) => await api(`/events/reviews/${selected.id}/${action}`, { method: "POST", headers: { "Content-Type": "application/json", [csrfHeader]: token }, body: JSON.stringify({ revision_id: selected.event_revision_id, reason: action === "reject" ? reason : null }) });
    try {
      let result: { data: undefined; response: Response };
      try { result = await request(csrf); }
      catch (error) { if (!(error instanceof AdminApiError) || error.status !== 401) throw error; result = await request(await renewCsrf()); }
      onCsrf(result.response.headers.get(csrfHeader) ?? ""); setSelected(null); await load();
      setDecisionMessage(action === "approve" ? "Событие одобрено и опубликовано." : "Событие отклонено, автор получит причину.");
    } catch (error) { setDecisionError(error instanceof AdminApiError && error.status === 409 ? "Заявка уже была обработана. Обновите очередь." : "Не удалось сохранить решение. Попробуйте ещё раз."); }
    finally { setBusy(false); }
  };
  return <section><header className="admin-page-header"><div><p>Проверка пользовательских событий</p><h1>Модерация</h1></div>{items && <span className="admin-live">{items.length} ожидают</span>}</header>{decisionMessage && <p className="success-message" role="status">{decisionMessage}</p>}
    {failed ? <AdminEmpty title="Очередь недоступна" text="Обновите страницу и попробуйте снова." /> : items === null ? <AdminStatus text="Загружаем очередь…" /> : !items.length ? <AdminEmpty title="Очередь пуста" text="Новых событий на проверке нет." /> : <div className="admin-table-wrap"><table><thead><tr><th>Событие</th><th>Автор</th><th>Город</th><th>Начало</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.title}</td><td>{item.display_name}</td><td>{item.city}</td><td>{new Date(item.starts_at).toLocaleString("ru-RU")}</td><td><button className="admin-table-action" disabled={busy} onClick={() => void open(item)}>Проверить</button></td></tr>)}</tbody></table></div>}
    {selected && <div className="admin-modal-backdrop" role="presentation"><section className="admin-review" role="dialog" aria-modal="true" aria-label="Проверка события"><button className="admin-close" onClick={() => setSelected(null)} aria-label="Закрыть">×</button><p>Событие от {selected.display_name} · ID {selected.public_id}</p><h2>{selected.title}</h2><img src={selected.photo_url} alt="Фото события" /><dl><div><dt>Категория</dt><dd>{selected.category}</dd></div><div><dt>Город</dt><dd>{selected.city}</dd></div><div><dt>Время</dt><dd>{new Date(selected.starts_at).toLocaleString("ru-RU")} — {new Date(selected.ends_at).toLocaleString("ru-RU")}</dd></div><div><dt>Адрес</dt><dd>{selected.normalized_address}{selected.landmark ? ` · ${selected.landmark}` : ""}</dd></div><div><dt>Видимость</dt><dd>{selected.address_visibility}</dd></div><div><dt>Лимит</dt><dd>{selected.capacity ?? "Без ограничения"}</dd></div></dl><h3>Описание</h3><p>{selected.description}</p>{decisionError && <p className="admin-form-error" role="alert">{decisionError}</p>}<div className="admin-review-actions"><button className="admin-approve" disabled={busy} onClick={() => void decide("approve")}>{busy ? "Сохраняем…" : "Одобрить"}</button><select value={reason} onChange={(event) => setReason(event.target.value as typeof reason)} aria-label="Причина отклонения">{rejectionReasons.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><button className="admin-reject" disabled={busy} onClick={() => void decide("reject")}>{busy ? "Сохраняем…" : "Отклонить"}</button></div></section></div>}
  </section>;
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
function formatBytes(value: number) { if (value < 1024 * 1024) return `${Math.round(value / 1024)} КБ`; if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} МБ`; return `${(value / 1024 / 1024 / 1024).toFixed(1)} ГБ`; }
function formatDuration(value: number) { const days = Math.floor(value / 86400); const hours = Math.floor((value % 86400) / 3600); return days ? `${days} д. ${hours} ч.` : `${hours} ч.`; }

class AdminApiError extends Error { constructor(public status: number) { super("Admin request failed"); } }
async function api<T = undefined>(path: string, init?: RequestInit): Promise<{ data: T; response: Response }> {
  const response = await fetch(`/api/admin${path}`, { ...init, credentials: "same-origin", headers: { Accept: "application/json", ...init?.headers } });
  if (!response.ok) throw new AdminApiError(response.status);
  const data = response.status === 204 ? undefined : await response.json();
  return { data: data as T, response };
}
