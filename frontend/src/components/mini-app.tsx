import {
  Bell,
  CalendarDays,
  ChevronRight,
  CircleUserRound,
  Heart,
  List,
  LoaderCircle,
  Map,
  MapPin,
  MessageCircleQuestion,
  Plus,
  RefreshCw,
  SearchX,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";

import type { AccountProfile } from "@/auth";
import { appConfig } from "@/config";
import { Button } from "@/components/ui/button";
import { AvatarCropper } from "@/components/avatar-cropper";
import type { MapCity, ResolvedLocation } from "@/components/event-map";

const EventMap = lazy(async () => ({ default: (await import("@/components/event-map")).EventMap }));

type Section = "events" | "people" | "create" | "notifications" | "profile";
type EventsMode = "map" | "list";
type PreviewState = "loading" | "error" | "empty" | null;
type AddressVisibility = "exact_public" | "exact_participants" | "street_only";

interface Category {
  id: string;
  slug: string;
  name: string;
  is_special: boolean;
  organizer_selectable: boolean;
}

interface Catalog {
  cities: MapCity[];
  categories: Category[];
}
interface ProfileEvent { id: string; title: string; starts_at: string; ends_at: string; category: string; role?: string | null }

const demoEvents = [
  { id: 1, category: "Особое", title: "Фестиваль на Родопском бульваре", time: "Сегодня, 17:00", place: "Родопский бульвар", people: 48, special: true },
  { id: 2, category: "Прогулки", title: "Закат у моря и новые знакомства", time: "Сегодня, 18:30", place: "городской пляж", people: 7 },
  { id: 3, category: "Игры", title: "Вечер настольных игр", time: "Завтра, 16:00", place: "ул. Коркмасова", people: 5 },
];

const demoPeople = [
  { id: 1, name: "Мадина", category: "Творчество", title: "Ищу компанию порисовать город", text: "Берём скетчбуки и встречаемся в центре. Опыт не важен.", likes: 12, questions: 3 },
  { id: 2, name: "Расул", category: "Спорт", title: "Нужны двое на волейбол", text: "Играем вечером после работы, спокойно и без соревнований.", likes: 8, questions: 1 },
  { id: 3, name: "Амина", category: "Обучение", title: "Практика английского за кофе", text: "Хочу собрать небольшую разговорную компанию на выходных.", likes: 16, questions: 4 },
];

export function MiniApp({ profile, csrfToken, onProfileUpdate, onLogout }: { profile: AccountProfile; csrfToken: string; onProfileUpdate: (profile: AccountProfile) => void; onLogout: () => Promise<void> }) {
  const initialPublicId = window.location.pathname.match(/^\/app\/profile\/(\d{8})$/)?.[1] ?? null;
  const [section, setSection] = useState<Section>(initialPublicId ? "profile" : "events");
  const [eventsMode, setEventsMode] = useState<EventsMode>("map");
  const [previewState, setPreviewState] = useState<PreviewState>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [selectedCity, setSelectedCity] = useState<MapCity | null>(null);
  const [choosingCity, setChoosingCity] = useState(false);

  useEffect(() => {
    let active = true;
    void fetch(`${appConfig.apiBaseUrl}/geo/catalog`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error("catalog unavailable");
        return await response.json() as Catalog;
      })
      .then((data) => {
        if (!active) return;
        setCatalog(data);
        setSelectedCity((current) => current ?? data.cities.find((city) => city.id === profile.selected_city_id) ?? data.cities[0] ?? null);
      })
      .catch(() => { if (active) setCatalogFailed(true); });
    return () => { active = false; };
  }, [profile.selected_city_id]);

  const selectSection = (next: Section) => {
    setPreviewState(null);
    setSection(next);
  };

  const saveCity = async (city: MapCity) => {
    setSelectedCity(city);
    setChoosingCity(false);
    const response = await fetch(`${appConfig.apiBaseUrl}/account/profile`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken }, body: JSON.stringify({ display_name: profile.display_name, bio: profile.bio, selected_city_id: city.id, version: profile.version ?? 1 }) });
    if (response.ok) onProfileUpdate(await response.json() as AccountProfile);
  };

  return (
    <main className="mini-app">
      <MiniHeader city={selectedCity} section={section} eventsMode={eventsMode} onModeChange={setEventsMode} onChooseCity={() => setChoosingCity(true)} />
      <div className="mini-content">
        {choosingCity ? (
          <CityChooser cities={catalog?.cities ?? []} selected={selectedCity} failed={catalogFailed} onSelect={(city) => void saveCity(city)} onClose={() => setChoosingCity(false)} />
        ) : previewState ? (
          <DemoState state={previewState} onClose={() => setPreviewState(null)} />
        ) : (
          <Suspense fallback={<DemoState state="loading" />}>
            {section === "events" && (eventsMode === "map" ? <EventMap embedded city={selectedCity ?? undefined} /> : <EventsList />)}
            {section === "people" && <PeopleList onCreate={() => setSection("create")} />}
            {section === "create" && <CreateScreen city={selectedCity} categories={catalog?.categories ?? []} catalogFailed={catalogFailed} onChooseCity={() => setChoosingCity(true)} onDone={() => setSection("events")} />}
            {section === "notifications" && <Notifications />}
            {section === "profile" && <Profile profile={profile} initialPublicId={initialPublicId} csrfToken={csrfToken} onUpdate={onProfileUpdate} onChooseCity={() => setChoosingCity(true)} onLogout={onLogout} onPreview={setPreviewState} />}
          </Suspense>
        )}
      </div>
      <BottomNav active={section} onSelect={selectSection} />
    </main>
  );
}

function MiniHeader({ city, section, eventsMode, onModeChange, onChooseCity }: { city: MapCity | null; section: Section; eventsMode: EventsMode; onModeChange: (mode: EventsMode) => void; onChooseCity: () => void }) {
  const titles: Record<Section, string> = { events: "События", people: "Ищу людей", create: "Создать", notifications: "Уведомления", profile: "Моё" };
  return (
    <header className="mini-header">
      <button className="city-button" type="button" onClick={onChooseCity}><MapPin aria-hidden="true" /><span><small>Город</small>{city?.name ?? "Выберите"}</span><ChevronRight aria-hidden="true" /></button>
      <strong>{titles[section]}</strong>
      {section === "events" ? (
        <div className="view-switch" aria-label="Вид событий">
          <button type="button" aria-label="Показать карту" aria-pressed={eventsMode === "map"} onClick={() => onModeChange("map")}><Map /></button>
          <button type="button" aria-label="Показать список" aria-pressed={eventsMode === "list"} onClick={() => onModeChange("list")}><List /></button>
        </div>
      ) : <span className="header-spacer" />}
    </header>
  );
}

function CityChooser({ cities, selected, failed, onSelect, onClose }: { cities: MapCity[]; selected: MapCity | null; failed: boolean; onSelect: (city: MapCity) => void; onClose: () => void }) {
  return <section className="feed city-chooser"><button className="text-back" type="button" onClick={onClose}>← Назад</button><p className="section-kicker">Город событий</p><h1>Выберите город</h1>{failed && <p className="form-error" role="alert">Не удалось загрузить города. Попробуйте открыть приложение снова.</p>}{cities.map((city) => <button className="menu-row" type="button" key={city.id} aria-current={selected?.id === city.id ? "true" : undefined} onClick={() => onSelect(city)}><span>{city.name}</span><ChevronRight /></button>)}<button className="menu-row unavailable-city" type="button" disabled><span>Другой город<small>Пока не поддерживается</small></span></button></section>;
}

function EventsList() {
  return <section className="feed" aria-label="Список событий"><p className="section-kicker">Рядом с вами · демо</p>{demoEvents.map((event) => <article className={`event-card${event.special ? " special-event" : ""}`} key={event.id}><div className="event-image" aria-hidden="true">{event.special ? <Sparkles /> : <CalendarDays />}</div><div className="event-copy"><span className="category-chip">{event.category}</span><h2>{event.title}</h2><p>{event.time} · {event.place}</p><span><Users aria-hidden="true" /> {event.people} собираются</span></div></article>)}</section>;
}

function PeopleList({ onCreate }: { onCreate: () => void }) {
  return <section className="feed" aria-label="Ищу людей"><div className="section-heading"><div><p className="section-kicker">Идеи живут 72 часа</p><h1>Найдите компанию</h1></div><Button onClick={onCreate}><Plus /> Идея</Button></div>{demoPeople.map((post) => <article className="people-card" key={post.id}><header><span className="demo-avatar">{post.name[0]}</span><div><strong>{post.name}</strong><small>сегодня, 12:30</small></div><span className="category-chip">{post.category}</span></header><h2>{post.title}</h2><p>{post.text}</p><footer><span><Heart /> {post.likes}</span><span><MessageCircleQuestion /> Вопросы и ответы · {post.questions}</span></footer></article>)}</section>;
}

function CreateScreen({ city, categories, catalogFailed, onChooseCity, onDone }: { city: MapCity | null; categories: Category[]; catalogFailed: boolean; onChooseCity: () => void; onDone: () => void }) {
  const [kind, setKind] = useState<"event" | "idea" | null>(null);
  const [categoryId, setCategoryId] = useState("");
  const [location, setLocation] = useState<ResolvedLocation | null>(null);
  const [visibility, setVisibility] = useState<AddressVisibility>("exact_public");
  const handleLocation = useCallback((next: ResolvedLocation | null) => setLocation(next), []);
  useEffect(() => setLocation(null), [city?.id]);
  useEffect(() => {
    if (location && !location.street && visibility !== "exact_public") setVisibility("exact_public");
  }, [location, visibility]);
  if (!kind) return <section className="centered-screen"><span className="big-icon"><Plus /></span><h1>Что создаём?</h1><p>Это демонстрация будущих форм. Данные пока никуда не отправляются.</p><div className="choice-grid"><button type="button" onClick={() => setKind("event")}><CalendarDays /><strong>Событие</strong><span>Место, время и участники</span></button><button type="button" onClick={() => setKind("idea")}><Users /><strong>Идею</strong><span>Найти людей без готового плана</span></button></div></section>;
  const selectableCategories = categories.filter((category) => category.organizer_selectable && !category.is_special);
  const canContinue = Boolean(categoryId && (kind === "idea" || location));
  const hiddenAddressUnavailable = Boolean(location && !location.street);
  return <section className="demo-form"><button className="text-back" type="button" onClick={() => setKind(null)}>← Назад</button><p className="section-kicker">Демонстрационная форма</p><h1>{kind === "event" ? "Новое событие" : "Новая идея"}</h1><button className="selected-city" type="button" onClick={onChooseCity}><MapPin /><span><small>Город</small>{city?.name ?? "Выберите город"}</span><ChevronRight /></button><label>Название<input placeholder={kind === "event" ? "Например, прогулка у моря" : "Кого и для чего вы ищете"} /></label><label>Категория<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="" disabled>Выберите категорию</option>{selectableCategories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}</select></label>{catalogFailed && <p className="form-error" role="alert">Категории временно недоступны.</p>}<label>Описание<textarea placeholder="Расскажите самое важное" maxLength={kind === "event" ? 1000 : 300} /></label>{kind === "event" && city && <><div className="location-picker"><p className="field-title">Место события</p><EventMap embedded selecting city={city} onLocationChange={handleLocation} /></div><fieldset className="visibility-options"><legend>Кто увидит точный адрес</legend><VisibilityOption value="exact_public" selected={visibility} onSelect={setVisibility} title="Все" text="Точное место сразу видно в карточке." /><VisibilityOption value="exact_participants" selected={visibility} onSelect={setVisibility} disabled={hiddenAddressUnavailable} title="Только участники" text="Остальные увидят только улицу." /><VisibilityOption value="street_only" selected={visibility} onSelect={setVisibility} disabled={hiddenAddressUnavailable} title="Только улица" text="Точное место останется доступно вам как организатору." />{hiddenAddressUnavailable && <p className="form-error">Для этой точки не удалось определить улицу, поэтому скрытые режимы недоступны.</p>}</fieldset></>}<Button disabled={!canContinue} onClick={onDone}>Посмотреть результат</Button><small>{kind === "event" && !location ? "Выберите подтверждённое место внутри города." : "На этом этапе форма ничего не сохраняет."}</small></section>;
}

function VisibilityOption({ value, selected, onSelect, title, text, disabled = false }: { value: AddressVisibility; selected: AddressVisibility; onSelect: (value: AddressVisibility) => void; title: string; text: string; disabled?: boolean }) {
  return <label className="visibility-option"><input type="radio" name="address-visibility" value={value} checked={selected === value} disabled={disabled} onChange={() => onSelect(value)} /><span><strong>{title}</strong><small>{text}</small></span></label>;
}

function Notifications() {
  return <section className="feed"><div className="section-heading"><div><p className="section-kicker">Демо</p><h1>Уведомления</h1></div><span className="unread-count">3 новых</span></div><h2 className="group-title">Нужно сделать</h2><Notification icon={<CalendarDays />} title="Подтвердите участие" text="Прогулка у моря · до 18:00" urgent /><h2 className="group-title">Сегодня</h2><Notification icon={<Bell />} title="Событие одобрено" text="Вечер настольных игр появился на карте" /><Notification icon={<Users />} title="Новый ответ" text="Амина ответила на ваш вопрос" /></section>;
}

function Notification({ icon, title, text, urgent = false }: { icon: React.ReactNode; title: string; text: string; urgent?: boolean }) {
  return <article className={`notification${urgent ? " urgent" : ""}`}><span>{icon}</span><div><strong>{title}</strong><p>{text}</p></div><ChevronRight /></article>;
}

function Profile({ profile, initialPublicId, csrfToken, onUpdate, onChooseCity, onLogout, onPreview }: { profile: AccountProfile; initialPublicId: string | null; csrfToken: string; onUpdate: (profile: AccountProfile) => void; onChooseCity: () => void; onLogout: () => Promise<void>; onPreview: (state: PreviewState) => void }) {
  const color = `hsl(${Number(profile.public_id.slice(-3)) % 360} 42% 42%)`;
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(profile.display_name);
  const [bio, setBio] = useState(profile.bio ?? "");
  const [lookup, setLookup] = useState(initialPublicId ?? "");
  const [publicProfile, setPublicProfile] = useState<AccountProfile | null>(null);
  const [message, setMessage] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [eventMode, setEventMode] = useState<"upcoming" | "completed" | null>(null);
  const save = async () => { if (!profile.selected_city_id) { onChooseCity(); return; } const response = await fetch(`${appConfig.apiBaseUrl}/account/profile`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken }, body: JSON.stringify({ display_name: name, bio, selected_city_id: profile.selected_city_id, version: profile.version ?? 1 }) }); if (response.ok) { onUpdate(await response.json() as AccountProfile); setEditing(false); setMessage("Профиль сохранён"); } else setMessage(response.status === 409 ? "Псевдоним можно менять раз в 7 дней" : "Не удалось сохранить профиль"); };
  const upload = async (file: Blob) => { const response = await fetch(`${appConfig.apiBaseUrl}/account/avatar`, { method: "PUT", credentials: "include", headers: { "Content-Type": file.type, "X-Afisha-CSRF": csrfToken }, body: file }); if (response.ok) { onUpdate(await response.json() as AccountProfile); setAvatarFile(null); } else setMessage("Не удалось обработать фотографию"); };
  const removeAvatar = async () => { const response = await fetch(`${appConfig.apiBaseUrl}/account/avatar`, { method: "DELETE", credentials: "include", headers: { "X-Afisha-CSRF": csrfToken } }); if (response.ok) onUpdate(await response.json() as AccountProfile); };
  const openPublic = useCallback(async () => { const response = await fetch(`${appConfig.apiBaseUrl}/profiles/${lookup}`, { credentials: "include" }); if (response.ok) { setPublicProfile(await response.json() as AccountProfile); window.history.pushState({}, "", `/app/profile/${lookup}`); } else setMessage("Профиль не найден"); }, [lookup]);
  useEffect(() => { if (initialPublicId) void openPublic(); }, [initialPublicId, openPublic]);
  if (publicProfile) return <PublicProfile profile={publicProfile} csrfToken={csrfToken} onBack={() => { setPublicProfile(null); window.history.pushState({}, "", "/app"); }} />;
  if (avatarFile) return <AvatarCropper file={avatarFile} onCancel={() => setAvatarFile(null)} onConfirm={(blob) => void upload(blob)} />;
  if (eventMode) return <AccountEvents state={eventMode} onBack={() => setEventMode(null)} />;
  return <section className="feed profile-screen"><div className="profile-card">{profile.avatar_url ? <img className="profile-avatar profile-photo" src={profile.avatar_url} alt="Ваш аватар" /> : <span className="profile-avatar" style={{ backgroundColor: color }}>{profile.display_name[0]}</span>}<div><p className="section-kicker">Ваш профиль</p><h1>{profile.display_name}</h1><p>ID <button className="copy-id" type="button" onClick={() => void navigator.clipboard.writeText(profile.public_id)}>{profile.public_id}</button> · {profile.organizer_status === "trusted" ? "Доверенный организатор" : "Новый организатор"}</p></div></div><div className="profile-stats"><div><strong>{profile.upcoming_count ?? 0}</strong><span>будущих</span></div><div><strong>{profile.completed_count ?? 0}</strong><span>завершено</span></div><div><strong>{profile.successful_events ?? 0}</strong><span>успешных</span></div></div>{editing ? <div className="profile-editor"><label>Псевдоним<input value={name} onChange={(event) => setName(event.target.value)} maxLength={32} /></label><label>О себе<textarea value={bio} onChange={(event) => setBio(event.target.value)} maxLength={150} /></label><button className="selected-city" type="button" onClick={onChooseCity}><MapPin /><span><small>Город</small>{profile.city_name ?? "Выберите"}</span><ChevronRight /></button><Button onClick={() => void save()}>Сохранить</Button></div> : <><p className="profile-bio">{profile.bio || "Описание пока не заполнено"}</p><Button onClick={() => setEditing(true)}>Редактировать профиль</Button></>}<div className="profile-photo-actions"><label className="file-picker"><span>Загрузить фотографию</span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) setAvatarFile(file); }} /></label>{profile.avatar_url && <Button variant="outline" onClick={() => void removeAvatar()}>Удалить фотографию</Button>}</div>{message && <p className="success-message" role="status">{message}</p>}<h2 className="group-title">События</h2><button className="menu-row" type="button" onClick={() => setEventMode("upcoming")}><span>Будущие события</span><ChevronRight /></button><button className="menu-row" type="button" onClick={() => setEventMode("completed")}><span>Завершённые события</span><ChevronRight /></button><h2 className="group-title">Открыть профиль</h2><div className="profile-lookup"><input inputMode="numeric" maxLength={8} placeholder="Восьмизначный номер" value={lookup} onChange={(event) => setLookup(event.target.value.replace(/\D/g, ""))} /><Button disabled={lookup.length !== 8} onClick={() => void openPublic()}>Открыть</Button></div><Button variant="outline" onClick={() => void onLogout()}>Выйти</Button><h2 className="group-title">Состояния экранов</h2><div className="state-buttons"><Button variant="outline" onClick={() => onPreview("loading")}>Загрузка</Button><Button variant="outline" onClick={() => onPreview("empty")}>Пусто</Button><Button variant="outline" onClick={() => onPreview("error")}>Ошибка</Button></div></section>;
}

function AccountEvents({ state, onBack }: { state: "upcoming" | "completed"; onBack: () => void }) {
  const [items, setItems] = useState<ProfileEvent[] | null>(null);
  useEffect(() => { void fetch(`${appConfig.apiBaseUrl}/account/events?state=${state}&limit=20`, { credentials: "include" }).then(async (response) => setItems(response.ok ? ((await response.json()) as { items: ProfileEvent[] }).items : [])); }, [state]);
  return <section className="feed"><button className="text-back" type="button" onClick={onBack}>← Назад</button><h1>{state === "upcoming" ? "Будущие события" : "Завершённые события"}</h1>{items === null ? <p>Загружаем…</p> : items.length ? items.map((event) => <article className="profile-event" key={event.id}><strong>{event.title}</strong><span>{event.role === "organizer" ? "Вы организатор" : "Вы участник"} · {event.category}</span></article>) : <p>Здесь пока пусто.</p>}</section>;
}

function PublicProfile({ profile, csrfToken, onBack }: { profile: AccountProfile; csrfToken: string; onBack: () => void }) {
  const [reason, setReason] = useState("photo"); const [comment, setComment] = useState(""); const [sent, setSent] = useState(false);
  const [upcoming, setUpcoming] = useState<ProfileEvent[]>([]); const [completed, setCompleted] = useState<ProfileEvent[]>([]); const [nextCompleted, setNextCompleted] = useState<number | null>(null);
  useEffect(() => { void Promise.all([fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/events?state=upcoming&limit=20`, { credentials: "include" }), fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/events?state=completed&limit=10`, { credentials: "include" })]).then(async ([future, history]) => { if (future.ok) setUpcoming(((await future.json()) as { items: ProfileEvent[] }).items); if (history.ok) { const data = await history.json() as { items: ProfileEvent[]; next_offset: number | null }; setCompleted(data.items); setNextCompleted(data.next_offset); } }); }, [profile.public_id]);
  const loadMore = async () => { if (nextCompleted === null) return; const response = await fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/events?state=completed&limit=10&offset=${nextCompleted}`, { credentials: "include" }); if (response.ok) { const data = await response.json() as { items: ProfileEvent[]; next_offset: number | null }; setCompleted((items) => [...items, ...data.items]); setNextCompleted(data.next_offset); } };
  const report = async () => { const response = await fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/reports`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken }, body: JSON.stringify({ reason, comment: comment || null }) }); if (response.ok) setSent(true); };
  return <section className="feed profile-screen"><button className="text-back" type="button" onClick={onBack}>← Назад</button><div className="profile-card">{profile.avatar_url ? <img className="profile-avatar profile-photo" src={profile.avatar_url} alt="Аватар пользователя" /> : <span className="profile-avatar">{profile.display_name[0]}</span>}<div><p className="section-kicker">Публичный профиль</p><h1>{profile.display_name}</h1><p>ID {profile.public_id} · {profile.organizer_status === "trusted" ? "Доверенный организатор" : "Новый организатор"}</p></div></div><p className="profile-bio">{profile.bio || "Описание не заполнено"}</p><h2 className="group-title">Будущие события</h2>{upcoming.length ? upcoming.map((event) => <article className="profile-event" key={event.id}><strong>{event.title}</strong><span>{event.category} · {new Date(event.starts_at).toLocaleDateString("ru-RU")}</span></article>) : <p className="state-hint">Опубликованных событий пока нет.</p>}<h2 className="group-title">Завершённые события</h2>{completed.length ? completed.map((event) => <article className="profile-event" key={event.id}><strong>{event.title}</strong><span>{event.category} · {new Date(event.ends_at).toLocaleDateString("ru-RU")}</span></article>) : <p className="state-hint">История пока пуста.</p>}{nextCompleted !== null && <Button variant="outline" onClick={() => void loadMore()}>Загрузить ещё</Button>}<h2 className="group-title">Пожаловаться на профиль</h2>{sent ? <p className="success-message">Жалоба отправлена</p> : <div className="profile-editor"><select value={reason} onChange={(event) => setReason(event.target.value)}><option value="photo">Фотография</option><option value="display_name">Псевдоним</option><option value="bio">Описание</option><option value="other">Другое</option></select>{reason === "other" && <textarea maxLength={300} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Опишите причину" />}<Button disabled={reason === "other" && !comment.trim()} onClick={() => void report()}>Отправить жалобу</Button></div>}</section>;
}

function DemoState({ state, onClose }: { state: Exclude<PreviewState, null>; onClose?: () => void }) {
  const content = { loading: { icon: <LoaderCircle className="spin" />, title: "Загружаем", text: "Секунду, собираем всё самое интересное." }, empty: { icon: <SearchX />, title: "Здесь пока пусто", text: "Можно создать первую встречу или посмотреть, кто ищет компанию." }, error: { icon: <RefreshCw />, title: "Не получилось загрузить", text: "Проверьте связь и попробуйте ещё раз. Ваши действия не потерялись." } }[state];
  return <section className="centered-screen state-screen" role={state === "error" ? "alert" : "status"}>{onClose && <button className="state-close" type="button" aria-label="Закрыть пример" onClick={onClose}><X /></button>}<span className="big-icon">{content.icon}</span><h1>{content.title}</h1><p>{content.text}</p>{state === "error" && <Button onClick={onClose}><RefreshCw /> Повторить</Button>}{state === "empty" && <Button onClick={onClose}><Plus /> Создать</Button>}</section>;
}

function BottomNav({ active, onSelect }: { active: Section; onSelect: (section: Section) => void }) {
  const items: Array<{ id: Section; label: string; icon: React.ReactNode }> = [{ id: "events", label: "События", icon: <Map /> }, { id: "people", label: "Ищу людей", icon: <Users /> }, { id: "create", label: "Создать", icon: <Plus /> }, { id: "notifications", label: "Новости", icon: <Bell /> }, { id: "profile", label: "Моё", icon: <CircleUserRound /> }];
  return <nav className="bottom-nav" aria-label="Основные разделы">{items.map((item) => <button className={item.id === "create" ? "create-nav" : ""} type="button" key={item.id} aria-current={active === item.id ? "page" : undefined} onClick={() => onSelect(item.id)}>{item.icon}<span>{item.label}</span>{item.id === "notifications" && <i aria-label="3 непрочитанных">3</i>}</button>)}</nav>;
}
