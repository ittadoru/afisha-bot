import {
  ArrowLeft,
  Bell,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  Heart,
  History,
  ImageOff,
  List,
  LoaderCircle,
  Map,
  MapPin,
  MessageCircleQuestion,
  MoreHorizontal,
  Plus,
  RefreshCw,
  SearchX,
  Send,
  Share2,
  Sparkles,
  TrendingUp,
  UserRoundSearch,
  Users,
  X,
} from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";

import type { AccountProfile } from "@/auth";
import { appConfig } from "@/config";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { TextBlink } from "@/components/ui/text-blink";
import type { MapCity } from "@/components/event-map";
import { EventCreation } from "@/components/event-creation";
import { EventChat } from "@/components/event-chat";
import { EventManagement } from "@/components/event-management";

const EventMap = lazy(async () => ({ default: (await import("@/components/event-map")).EventMap }));

type Section = "events" | "people" | "create" | "notifications" | "profile";
type EventsMode = "map" | "list";
type PreviewState = "loading" | "error" | "empty" | null;
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
type PublicEvent = {
  id: string; kind: "regular" | "special"; lifecycle_status?: string;
  category: string; category_slug: string; title: string; description: string;
  starts_at: string; ends_at: string; visible_address: string;
  participant_count: number; capacity: number | null; available_places: number | null;
  interest_count: number; viewer_interested?: boolean;
  viewer_is_organizer?: boolean;
  viewer_membership?: "none" | "participating" | "waitlisted" | "excluded";
  queue_position?: number | null;
  photo_url: string; organizer_public_id: string | null;
  organizer_name: string | null; organizer_status: string | null;
  cancellation_reason_code?: string | null; latitude?: number | null; longitude?: number | null;
  chat_enabled?: boolean;
};

type LookingPost = { id: string; title: string; body: string; category: string; created_at: string; like_count: number; question_count: number; viewer_liked: boolean; is_author: boolean; status: "active" | "expired" | "hidden"; remaining_seconds: number; author: { display_name: string; avatar_url: string | null } };
type NotificationItem = { id: string; title: string; body: string; importance: string; read_at: string | null };

export function MiniApp({ profile, csrfToken, onProfileUpdate, onLogout }: { profile: AccountProfile; csrfToken: string; onProfileUpdate: (profile: AccountProfile) => void; onLogout: () => Promise<void> }) {
  const initialPublicId = window.location.pathname.match(/^\/app\/profile\/(\d{8})$/)?.[1] ?? null;
  const initialEventId = window.location.pathname.match(/^\/app\/event\/([0-9a-f-]{36})$/i)?.[1] ?? null;
  const initialChatEventId = window.location.pathname.match(/^\/app\/event\/([0-9a-f-]{36})\/chat$/i)?.[1] ?? null;
  const initialLookingPostId = window.location.pathname.match(/^\/app\/looking\/([0-9a-f-]{36})$/i)?.[1] ?? null;
  const [section, setSection] = useState<Section>(initialPublicId ? "profile" : "events");
  const [lastHomeSection, setLastHomeSection] = useState<"events" | "people">("events");
  const [eventsMode, setEventsMode] = useState<EventsMode>("map");
  const [createKind, setCreateKind] = useState<"event" | "idea">("event");
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [previewState, setPreviewState] = useState<PreviewState>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [selectedCity, setSelectedCity] = useState<MapCity | null>(null);
  const [choosingCity, setChoosingCity] = useState(false);
  const [citySaving, setCitySaving] = useState(false);
  const [savingCityId, setSavingCityId] = useState<string | null>(null);
  const [cityError, setCityError] = useState("");
  const [createDirty, setCreateDirty] = useState(false);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(initialEventId ?? initialChatEventId);
  const [selectedLookingPostId, setSelectedLookingPostId] = useState<string | null>(initialLookingPostId);
  const [chatOpen, setChatOpen] = useState(Boolean(initialChatEventId));
  const [streetGroup, setStreetGroup] = useState<{ ids: string[]; street: string } | null>(null);
  const createDiscardRef = useRef<(() => Promise<void>) | null>(null);
  const registerCreateDiscard = useCallback((discard: (() => Promise<void>) | null) => { createDiscardRef.current = discard; }, []);
  const openEvent = useCallback((id: string) => {
    setSelectedEventId(id);
    setChatOpen(false);
    window.history.pushState({}, "", `/app/event/${id}`);
  }, []);
  const closeEvent = useCallback(() => {
    setSelectedEventId(null);
    setChatOpen(false);
    window.history.pushState({}, "", "/app");
  }, []);
  const openChat = useCallback((id: string) => {
    setChatOpen(true);
    window.history.pushState({}, "", `/app/event/${id}/chat`);
  }, []);
  const closeLookingPost = useCallback(() => {
    setSelectedLookingPostId(null);
    window.history.pushState({}, "", "/app");
  }, []);
  const openStreetGroup = useCallback((ids: string[], street: string) => {
    setStreetGroup({ ids, street });
  }, []);
  const openEventsList = useCallback(() => setEventsMode("list"), []);

  const refreshUnreadNotifications = useCallback(() => {
    void fetch(`${appConfig.apiBaseUrl}/account/notifications`, { credentials: "include" })
      .then(async (response) => response.ok ? await response.json() as Array<{ read_at: string | null }> : [])
      .then((items) => setUnreadNotifications(items.filter((item) => !item.read_at).length))
      .catch(() => undefined);
  }, []);

  useEffect(() => { refreshUnreadNotifications(); }, [refreshUnreadNotifications]);

  useEffect(() => {
    const scrollFocusedField = (event?: Event) => {
      const active = event?.target ?? document.activeElement;
      if (!(active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement || active instanceof HTMLSelectElement)) return;
      const fieldElement = active;
      window.setTimeout(() => {
        const content = fieldElement.closest<HTMLElement>(".scroll-focus-container") ?? document.querySelector<HTMLElement>(".mini-content");
        if (!content) return;
        const field = fieldElement.getBoundingClientRect();
        const area = content.getBoundingClientRect();
        content.scrollBy({ top: field.top - area.top - area.height / 2 + field.height / 2, behavior: "auto" });
      }, 120);
    };
    document.addEventListener("focusin", scrollFocusedField);
    window.addEventListener("miniappviewportchange", scrollFocusedField);
    return () => { document.removeEventListener("focusin", scrollFocusedField); window.removeEventListener("miniappviewportchange", scrollFocusedField); };
  }, []);

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
  // The catalog is static while the Mini App stays open. Re-fetching it after
  // PATCH city causes a second, needless map reload.
  }, []);

  const leaveCreate = async (): Promise<boolean> => {
    if (section !== "create" || !createDirty) return true;
    if (!await confirmFormLoss()) return false;
    await createDiscardRef.current?.();
    setCreateDirty(false);
    return true;
  };

  const selectSection = async (next: Section) => {
    if (next !== "create" && !await leaveCreate()) return;
    setPreviewState(null);
    if (next === "events" || next === "people") setLastHomeSection(next);
    setSection(next);
  };

  const createForMode = async () => {
    const kind = section === "people" ? "idea" : "event";
    setCreateKind(kind);
    await selectSection("create");
  };

  const openCityChooser = async () => {
    setCityError("");
    setChoosingCity(true);
  };

  const saveCity = async (city: MapCity) => {
    if (citySaving || city.id === selectedCity?.id) { setChoosingCity(false); return; }
    setCitySaving(true); setSavingCityId(city.id); setCityError("");
    const request = async (version: number) => await fetch(`${appConfig.apiBaseUrl}/account/profile/city`, {
      method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken },
      body: JSON.stringify({ selected_city_id: city.id, version }),
    });
    try {
      let response = await request(profile.version ?? 1);
      if (response.status === 409) {
        const current = await fetch(`${appConfig.apiBaseUrl}/account/profile`, { credentials: "include" });
        if (current.ok) response = await request((await current.json() as AccountProfile).version ?? 1);
      }
      if (!response.ok) throw new Error(String(response.status));
      const updated = await response.json() as AccountProfile;
      onProfileUpdate(updated);
      setSelectedCity(city);
      setChoosingCity(false);
    } catch (error) {
      setCityError(error instanceof Error && error.message === "422" ? "Этот город сейчас недоступен." : "Не удалось сменить город. Повторите попытку.");
    } finally { setCitySaving(false); setSavingCityId(null); }
  };

  useEffect(() => {
    const backButton = window.Telegram?.WebApp?.BackButton;
    if (!backButton || !choosingCity) return;
    const close = () => { if (!citySaving) setChoosingCity(false); };
    backButton.onClick?.(close);
    backButton.show?.();
    return () => {
      backButton.offClick?.(close);
      backButton.hide?.();
    };
  }, [choosingCity, citySaving]);

  return (
    <main className={`mini-app${choosingCity ? " city-chooser-active" : ""}`}>
      {choosingCity ? <CityChooser cities={catalog?.cities ?? []} selected={selectedCity} failed={catalogFailed} saving={citySaving} savingCityId={savingCityId} error={cityError} onSelect={(city) => void saveCity(city)} onClose={() => { if (!citySaving) setChoosingCity(false); }} /> : selectedEventId || selectedLookingPostId ? (
        <div className="mini-content page-mode">
          {selectedEventId
            ? (chatOpen
              ? <EventChat eventId={selectedEventId} csrfToken={csrfToken} onClose={() => { setChatOpen(false); window.history.pushState({}, "", `/app/event/${selectedEventId}`); }} />
              : <EventPage eventId={selectedEventId} csrfToken={csrfToken} onClose={closeEvent} onOpenChat={() => openChat(selectedEventId)} />)
            : <LookingPostSheet postId={selectedLookingPostId ?? ""} csrfToken={csrfToken} onClose={closeLookingPost} />}
        </div>
      ) : <>
      {(section === "events" || section === "people") ? <HomeTopBar profile={profile} eventsMode={eventsMode} showViewSwitch={section === "events"} unread={unreadNotifications} onModeChange={setEventsMode} onProfile={() => void selectSection("profile")} onNotifications={() => { refreshUnreadNotifications(); void selectSection("notifications"); }} /> : <SubpageHeader title={{ create: createKind === "event" ? "Новое событие" : "Новая идея", notifications: "Уведомления", profile: "Профиль", events: "События", people: "Ищу людей" }[section]} onBack={() => void selectSection(section === "create" ? createKind === "idea" ? "people" : "events" : lastHomeSection)} />}
      <div className={`mini-content${section === "events" && eventsMode === "map" ? " map-mode" : ""}${section === "people" ? " people-mode" : ""}${section === "events" || section === "people" ? " home-mode" : " subpage-mode"}`}>
        {previewState ? (
          <DemoState state={previewState} onClose={() => setPreviewState(null)} />
        ) : (
          <Suspense fallback={<DemoState state="loading" />}>
            {section === "events" && (eventsMode === "map" ? <EventMap embedded city={selectedCity ?? undefined} onOpenEvent={openEvent} onOpenStreetGroup={openStreetGroup} onOpenList={openEventsList} /> : <EventsList city={selectedCity} onOpen={openEvent} />)}
            {section === "people" && <PeopleList city={selectedCity} csrfToken={csrfToken} onCreate={() => setSection("create")} onOpen={(id) => { setSelectedLookingPostId(id); window.history.pushState({}, "", `/app/looking/${id}`); }} />}
            {section === "create" && <CreateScreen initialKind={createKind} city={selectedCity} categories={catalog?.categories ?? []} catalogFailed={catalogFailed} csrfToken={csrfToken} organizerStatus={profile.organizer_status === "trusted" ? "trusted" : "new"} onDirtyChange={setCreateDirty} registerDiscard={registerCreateDiscard} onChooseCity={() => void openCityChooser()} onExit={() => setSection(createKind === "idea" ? "people" : "events")} onDone={() => { setCreateDirty(false); setSection(createKind === "idea" ? "people" : "events"); }} />}
            {section === "notifications" && <Notifications onUnreadChange={setUnreadNotifications} />}
            {section === "profile" && <Profile profile={profile} city={selectedCity} onChooseCity={() => void openCityChooser()} initialPublicId={initialPublicId} csrfToken={csrfToken} onUpdate={onProfileUpdate} onLogout={onLogout} onPreview={setPreviewState} />}
          </Suspense>
        )}
      </div>
      {(section === "events" || section === "people") && <HomeModeDock active={section} onSelect={(next) => void selectSection(next)} onCreate={() => void createForMode()} />}
      </>}
      {streetGroup && <StreetGroupSheet group={streetGroup} onClose={() => setStreetGroup(null)} onOpen={(id) => { setStreetGroup(null); openEvent(id); }} />}
    </main>
  );

}

function EventPhoto({ src, className, alt = "" }: { src: string; className?: string; alt?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <span className={`${className ?? ""} image-placeholder`} role="img" aria-label="Фотография недоступна"><ImageOff aria-hidden="true" /></span>;
  return <img className={className} src={src} alt={alt} onError={() => setFailed(true)} />;
}

function HomeTopBar({ profile, eventsMode, showViewSwitch, unread, onModeChange, onProfile, onNotifications }: { profile: AccountProfile; eventsMode: EventsMode; showViewSwitch: boolean; unread: number; onModeChange: (mode: EventsMode) => void; onProfile: () => void; onNotifications: () => void }) {
  return <header className="home-top-bar" aria-label="Навигация главного экрана">
    <button className="floating-round-control avatar-control" type="button" aria-label="Открыть профиль" onClick={onProfile}>
      {profile.avatar_url ? <img src={profile.avatar_url} alt="" /> : <span>{profile.display_name[0]}</span>}
    </button>
    {showViewSwitch ? <div className="floating-segment view-segment" role="group" aria-label="Вид событий">
      <button type="button" aria-pressed={eventsMode === "map"} onClick={() => onModeChange("map")}><Map aria-hidden="true" />Карта</button>
      <button type="button" aria-pressed={eventsMode === "list"} onClick={() => onModeChange("list")}><List aria-hidden="true" />Список</button>
    </div> : <span className="home-mode-title"><UserRoundSearch aria-hidden="true" />Ищу людей</span>}
    <button className="floating-round-control notification-control" type="button" aria-label={`Открыть уведомления${unread ? `. Непрочитанных: ${unread}` : ""}`} onClick={onNotifications}>
      <Bell aria-hidden="true" />
      {unread > 0 && <span className="notification-badge" aria-hidden="true">{unread > 9 ? "9+" : unread}</span>}
    </button>
  </header>;
}

function SubpageHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return <header className="subpage-header"><button type="button" aria-label="Вернуться на главный экран" onClick={onBack}><ArrowLeft aria-hidden="true" /></button><strong>{title}</strong><span aria-hidden="true" /></header>;
}

function HomeModeDock({ active, onSelect, onCreate }: { active: "events" | "people"; onSelect: (section: "events" | "people") => void; onCreate: () => void }) {
  return <div className="home-bottom-controls">
    <div className="floating-segment mode-segment" role="group" aria-label="Разделы главного экрана">
      <button type="button" aria-pressed={active === "events"} onClick={() => onSelect("events")}><CalendarDays aria-hidden="true" />События</button>
      <button type="button" aria-pressed={active === "people"} onClick={() => onSelect("people")}><Users aria-hidden="true" />Ищу людей</button>
    </div>
    <button className="create-fab" type="button" aria-label={active === "events" ? "Создать событие" : "Создать объявление"} onClick={onCreate}><Plus aria-hidden="true" /></button>
  </div>;
}

function CityChooser({ cities, selected, failed, saving, savingCityId, error, onSelect, onClose }: { cities: MapCity[]; selected: MapCity | null; failed: boolean; saving: boolean; savingCityId: string | null; error: string; onSelect: (city: MapCity) => void; onClose: () => void }) {
  return <section className="city-chooser-screen"><header className="city-chooser-header"><button type="button" disabled={saving} onClick={onClose}><ArrowLeft aria-hidden="true" /> Назад</button><strong>Выберите город</strong><span /></header><div className="city-chooser-list scroll-focus-container">{failed && <p className="form-error" role="alert">Не удалось загрузить города. Попробуйте открыть приложение снова.</p>}{error && <p className="form-error" role="alert">{error}</p>}{cities.map((city) => <button className="menu-row city-choice" type="button" disabled={saving} key={city.id} aria-current={selected?.id === city.id ? "true" : undefined} onClick={() => onSelect(city)}><span>{city.name}</span>{savingCityId === city.id ? <LoaderCircle className="spin" aria-label="Сохраняем" /> : selected?.id === city.id ? <Check aria-label="Выбран" /> : <ChevronRight />}</button>)}<button className="menu-row unavailable-city" type="button" disabled><span>Другой город<small>Пока не поддерживается</small></span></button></div></section>;
}

function EventsList({ city, onOpen }: { city: MapCity | null; onOpen: (id: string) => void }) {
  const [items, setItems] = useState<PublicEvent[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!city) { setItems([]); return; }
    setItems(null); setFailed(false);
    void fetch(`${appConfig.apiBaseUrl}/events?city_id=${encodeURIComponent(city.id)}&view=list`, { credentials: "include" })
      .then(async (response) => { if (!response.ok) throw new Error(); return await response.json() as { items: PublicEvent[] }; })
      .then((data) => setItems(data.items)).catch(() => { setFailed(true); setItems([]); });
  }, [city]);
  if (failed) return <DemoState state="error" />;
  if (items === null) return <section className="feed home-events-list" role="status"><TextBlink className="text-blink">Собираем события…</TextBlink><div className="card-list-skeleton" aria-hidden="true"><span /><span /><span /></div></section>;
  if (!items.length) return <section className="feed home-events-list" aria-label="Список событий"><p className="section-kicker">Афиша · {city?.name}</p><h1>События рядом</h1><DecorativeEmpty title={`Пока тихо${city?.name ? ` в городе ${city.name}` : ""}`} text="Первое событие может начаться с вашей идеи." /></section>;
  const [featured, ...rest] = [...items].sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
  const grouped = groupEventsByDate(rest);
  return <section className="feed home-events-list" aria-label="Список событий">
    <p className="section-kicker">Афиша · {city?.name}</p><h1>События рядом</h1>
    <button type="button" className={`featured-event category-${featured.category_slug}`} onClick={() => onOpen(featured.id)}>
      <EventPhoto className="featured-event-photo" src={featured.photo_url} alt={`Фотография события «${featured.title}»`} />
      <span className="featured-event-shade" aria-hidden="true" />
      <span className="featured-event-content"><span className="category-chip">{featured.category}</span>{featured.kind === "special" && <small><Sparkles aria-hidden="true" /> Общественное</small>}<strong>{featured.title}</strong><span><CalendarDays aria-hidden="true" /> {formatEventTime(featured.starts_at)}</span><span><MapPin aria-hidden="true" /> {featured.visible_address}</span></span>
    </button>
    {grouped.map(([label, events]) => <section className="event-date-group" key={label}><h2>{label}</h2><div>{events.map((event) => <button type="button" className={`editorial-event-row category-${event.category_slug}`} key={event.id} onClick={() => onOpen(event.id)}><EventPhoto className="event-row-photo" src={event.photo_url} alt="" /><span className="event-row-copy"><small><span className="category-dot" aria-hidden="true" />{event.category}{event.kind === "special" ? " · Общественное" : ""}</small><strong>{event.title}</strong><span>{formatEventClock(event.starts_at)} · {event.visible_address}</span><span><Users aria-hidden="true" /> {event.participant_count} собираются</span></span><ChevronRight aria-hidden="true" /></button>)}</div></section>)}
  </section>;
}

function groupEventsByDate(items: PublicEvent[]): Array<[string, PublicEvent[]]> {
  const groups = new globalThis.Map<string, PublicEvent[]>();
  items.forEach((item) => {
    const key = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Moscow", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(item.starts_at));
    groups.set(key, [...(groups.get(key) ?? []), item]);
  });
  return [...groups.entries()].map(([key, events]) => [eventDateLabel(key), events]);
}

function eventDateLabel(key: string): string {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Moscow", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const tomorrow = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Moscow", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(Date.now() + 86_400_000));
  if (key === today) return "Сегодня";
  if (key === tomorrow) return "Завтра";
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", weekday: "long", day: "numeric", month: "long" }).format(new Date(`${key}T12:00:00+03:00`));
}

function formatEventClock(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function PeopleList({ city, csrfToken, onCreate, onOpen }: { city: MapCity | null; csrfToken: string; onCreate: () => void; onOpen: (id: string) => void }) {
  const [items, setItems] = useState<LookingPost[] | null>(null); const [failed, setFailed] = useState(false); const [moreFailed, setMoreFailed] = useState(false); const [loadingMore, setLoadingMore] = useState(false); const [nextCursor, setNextCursor] = useState<string | null>(null); const [likeBusy, setLikeBusy] = useState<string | null>(null); const [sort, setSort] = useState<"new" | "old" | "popular">("new");
  const load = useCallback(async (append = false) => { if (!city) { setItems([]); return; } if (!append) { setItems(null); setFailed(false); } else { setLoadingMore(true); setMoreFailed(false); } try { const suffix = append && nextCursor ? `&cursor=${encodeURIComponent(nextCursor)}` : ""; const r = await fetch(`${appConfig.apiBaseUrl}/looking-posts?city_id=${encodeURIComponent(city.id)}&sort=${sort}${suffix}`, { credentials: "include" }); if (!r.ok) throw new Error(); const data = await r.json() as { items: LookingPost[]; next_cursor: string | null }; setItems((current) => append ? [...(current ?? []), ...data.items].filter((item, index, all) => all.findIndex((other) => other.id === item.id) === index) : data.items); setNextCursor(data.next_cursor); } catch { if (append) setMoreFailed(true); else { setFailed(true); setItems([]); } } finally { setLoadingMore(false); } }, [city, nextCursor, sort]);
  useEffect(() => { void load(); }, [city, sort]);
  const like = async (post: LookingPost) => { if (likeBusy || post.is_author || post.status !== "active") return; setLikeBusy(post.id); const r = await fetch(`${appConfig.apiBaseUrl}/looking-posts/${post.id}/like`, { method: post.viewer_liked ? "DELETE" : "PUT", credentials: "include", headers: { "X-Afisha-CSRF": csrfToken } }); setLikeBusy(null); if (r.ok) void load(); };
  const statusText = (post: LookingPost) => post.status === "active" ? `Активна · осталось ${Math.max(1, Math.ceil(post.remaining_seconds / 3600))} ч` : post.status === "expired" ? "Срок публикации истёк" : "Скрыта модерацией";
  return <section className="people-screen" aria-label="Ищу людей"><div className="people-toolbar"><div className="section-heading"><div><p className="section-kicker">Идеи живут 72 часа</p><h1>Найдите компанию</h1></div></div><div className="view-switch people-sort" role="group" aria-label="Сортировка"><button type="button" aria-pressed={sort === "new"} onClick={() => setSort("new")}><Clock3 aria-hidden="true" />Новые</button><button type="button" aria-pressed={sort === "old"} onClick={() => setSort("old")}><History aria-hidden="true" />Старые</button><button type="button" aria-pressed={sort === "popular"} onClick={() => setSort("popular")}><TrendingUp aria-hidden="true" />Популярные</button></div></div><div className="people-list-scroll scroll-focus-container">{failed ? <CompactListState title="Не удалось загрузить идеи" action="Повторить" onAction={() => void load()} /> : items === null ? <><TextBlink className="text-blink">Ищем людей рядом…</TextBlink><div className="card-list-skeleton" role="status" aria-label="Загружаем идеи"><span /><span /><span /></div></> : items.length ? <>{items.map((post) => <article className="people-card" key={post.id} role="button" tabIndex={0} aria-label={`${post.title}. Автор ${post.author.display_name}`} onClick={() => onOpen(post.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onOpen(post.id); } }}>{post.author.avatar_url ? <img className="demo-avatar" src={post.author.avatar_url} alt="" /> : <span className="demo-avatar">{post.author.display_name[0]}</span>}<header><div><strong>{post.author.display_name}</strong><small>{new Date(post.created_at).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" })}</small></div><span className="category-chip">{post.category}</span></header><h2>{post.title}</h2><p>{post.body}</p><small className="idea-status"><span aria-hidden="true">●</span> {statusText(post)}</small><footer><button type="button" aria-label={`${post.viewer_liked ? "Убрать отметку нравится" : "Отметить нравится"}. Всего ${post.like_count}`} disabled={Boolean(likeBusy) || post.is_author || post.status !== "active"} onClick={(event) => { event.stopPropagation(); void like(post); }} aria-pressed={post.viewer_liked}><Heart aria-hidden="true" /> {post.like_count}</button><span><MessageCircleQuestion aria-hidden="true" /> Вопросы и ответы · {post.question_count}</span></footer></article>)}{nextCursor && <Button variant="outline" disabled={loadingMore} onClick={() => void load(true)}>{loadingMore ? "Загружаем…" : "Показать ещё"}</Button>}{moreFailed && <p className="form-error">Не удалось загрузить ещё. Нажмите «Показать ещё», чтобы повторить.</p>}</> : <CompactListState title="В этом городе пока нет идей" action="Создать идею" onAction={onCreate} />}</div></section>;
}

function CompactListState({ title, action, onAction }: { title: string; action: string; onAction: () => void }) {
  return <div className="compact-list-state"><p>{title}</p><Button variant="outline" onClick={onAction}>{action}</Button></div>;
}

function LookingPostSheet({ postId, csrfToken, onClose }: { postId: string; csrfToken: string; onClose: () => void }) {
  type Question = { id: string; question: string; answer?: string; asker?: { display_name: string } };
  const [post, setPost] = useState<LookingPost | null>(null); const [questions, setQuestions] = useState<Question[]>([]); const [pending, setPending] = useState<Question[]>([]); const [question, setQuestion] = useState(""); const [answers, setAnswers] = useState<Record<string, string>>({}); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false); const [menuOpen, setMenuOpen] = useState(false); const askKey = useRef<string | null>(null); const answerKeys = useRef<Record<string, string>>({});
  const load = useCallback(async () => { const [detail, qa] = await Promise.all([fetch(`${appConfig.apiBaseUrl}/looking-posts/${postId}`, { credentials: "include" }), fetch(`${appConfig.apiBaseUrl}/looking-posts/${postId}/questions`, { credentials: "include" })]); if (detail.ok) setPost(await detail.json() as LookingPost); if (qa.ok) { const data = await qa.json() as { items: Question[]; pending: Question[] }; setQuestions(data.items); setPending(data.pending); } }, [postId]);
  useEffect(() => { void load(); }, [load]);
  const ask = async () => { if (busy) return; setBusy(true); const key = askKey.current ?? crypto.randomUUID(); askKey.current = key; const r = await fetch(`${appConfig.apiBaseUrl}/looking-posts/${postId}/questions`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, "Idempotency-Key": key }, body: JSON.stringify({ question }) }); setBusy(false); if (r.ok) { askKey.current = null; setQuestion(""); setMessage("Вопрос отправлен автору."); void load(); } else setMessage(r.status === 409 ? "На эту идею уже отправлен вопрос, ожидающий ответа." : "Не удалось отправить вопрос."); };
  const answer = async (questionId: string) => { const value = answers[questionId]?.trim(); if (!value || busy) return; setBusy(true); const key = answerKeys.current[questionId] ?? crypto.randomUUID(); answerKeys.current[questionId] = key; const r = await fetch(`${appConfig.apiBaseUrl}/looking-posts/${postId}/questions/${questionId}/answer`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, "Idempotency-Key": key }, body: JSON.stringify({ answer: value }) }); setBusy(false); if (r.ok) { delete answerKeys.current[questionId]; setMessage("Ответ опубликован."); void load(); } else setMessage(r.status === 409 ? "На этот вопрос уже ответили." : "Не удалось сохранить ответ."); };
  const withdraw = async () => { if (!post || busy || !confirm("Снять идею с публикации?")) return; setBusy(true); const response = await fetch(`${appConfig.apiBaseUrl}/looking-posts/${postId}`, { method: "DELETE", credentials: "include", headers: { "X-Afisha-CSRF": csrfToken } }); setBusy(false); if (response.ok) { setMessage("Идея снята с публикации."); void load(); } else setMessage("Не удалось снять идею."); };
  const statusText = post?.status === "active" ? `Активна · осталось ${Math.max(1, Math.ceil((post?.remaining_seconds ?? 0) / 3600))} ч` : post?.status === "expired" ? "Срок публикации истёк" : "Скрыта модерацией";
  return <section className={`looking-detail${post && !post.is_author && post.status === "active" ? " has-composer" : ""}`}>
    <header className="detail-appbar"><button type="button" aria-label="Назад" onClick={onClose}><ArrowLeft aria-hidden="true" /></button><strong>Ищу людей</strong><div className="detail-menu-wrap">{post?.is_author && post.status === "active" ? <><button type="button" aria-label="Действия с идеей" aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}><MoreHorizontal aria-hidden="true" /></button>{menuOpen && <div className="detail-overflow-menu"><button type="button" disabled={busy} onClick={() => { setMenuOpen(false); void withdraw(); }}>Снять идею</button></div>}</> : <span />}</div></header>
    {post ? <><div className="looking-detail-scroll">
      <header className="idea-detail-author">{post.author.avatar_url ? <img className="demo-avatar" src={post.author.avatar_url} alt="" /> : <span className="demo-avatar">{post.author.display_name[0]}</span>}<span><strong>{post.author.display_name}</strong><small>{new Date(post.created_at).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}</small></span><span className="category-chip">{post.category}</span></header>
      <div className="idea-detail-intro"><h1>{post.title}</h1><p>{post.body}</p><span className="idea-status"><i aria-hidden="true" />{statusText}</span></div>
      <section className="qa-section"><header><span><MessageCircleQuestion aria-hidden="true" /></span><div><p className="section-kicker">Обсуждение</p><h2>Вопросы и ответы</h2></div><small>{questions.length + pending.length}</small></header>
        {questions.length ? <div className="qa-list">{questions.map((item) => <article className="qa-card" key={item.id}><span className="qa-label">Вопрос</span><strong>{item.question}</strong><div><span className="qa-label">Ответ автора</span><p>{item.answer}</p></div></article>)}</div> : pending.length === 0 && <p className="qa-empty">Пока вопросов нет. Можно начать разговор первым.</p>}
        {pending.length > 0 && <div className="qa-pending"><h3>{post.is_author ? "Ждут вашего ответа" : "Ожидает ответа автора"}</h3>{pending.map((item) => <article className="qa-card pending" key={item.id}>{post.is_author && item.asker && <small>{item.asker.display_name}</small>}<span className="qa-label">Вопрос</span><strong>{item.question}</strong>{post.is_author && post.status === "active" && <div className="qa-answer-form"><label htmlFor={`answer-${item.id}`}>Ваш ответ</label><textarea id={`answer-${item.id}`} value={answers[item.id] ?? ""} onChange={(event) => setAnswers({ ...answers, [item.id]: event.target.value })} maxLength={300} placeholder="Ответьте коротко и по делу" /><Button disabled={busy || !answers[item.id]?.trim()} onClick={() => void answer(item.id)}>Опубликовать ответ</Button></div>}</article>)}</div>}
      </section>
      {message && <p className="inline-feedback" role="status">{message}</p>}
    </div>
    {!post.is_author && post.status === "active" && <form className="qa-composer" onSubmit={(event) => { event.preventDefault(); void ask(); }}><label className="sr-only" htmlFor="qa-question">Ваш вопрос</label><textarea id="qa-question" rows={1} value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={200} placeholder="Задайте вопрос автору" /><button type="submit" aria-label="Отправить вопрос" disabled={busy || !question.trim()}><Send aria-hidden="true" /></button></form>}</> : <DemoState state="loading" />}
  </section>;
}

function CreateScreen({ initialKind, city, categories, catalogFailed, csrfToken, organizerStatus, onDirtyChange, registerDiscard, onChooseCity, onExit, onDone }: { initialKind: "event" | "idea"; city: MapCity | null; categories: Category[]; catalogFailed: boolean; csrfToken: string; organizerStatus: "new" | "trusted"; onDirtyChange: (dirty: boolean) => void; registerDiscard: (discard: (() => Promise<void>) | null) => void; onChooseCity: () => void; onExit: () => void; onDone: () => void }) {
  const kind = initialKind;
  const [categoryId, setCategoryId] = useState("");
  const selectableCategories = categories.filter((category) => category.organizer_selectable && !category.is_special);
  if (kind === "event") {
    if (!city) return <section className="centered-screen"><MapPin /><h1>Сначала выберите город</h1><Button onClick={onChooseCity}>Выбрать город</Button></section>;
    if (catalogFailed) return <section className="centered-screen"><SearchX /><h1>Категории недоступны</h1><p>Откройте приложение снова и повторите попытку.</p></section>;
    return <EventCreation city={city} categories={categories} csrfToken={csrfToken} organizerStatus={organizerStatus} onDirtyChange={onDirtyChange} registerDiscard={registerDiscard} onChooseCity={onChooseCity} onCancel={onExit} onFinished={onDone} />;
  }
  return <LookingPostCreation city={city} categories={selectableCategories} csrfToken={csrfToken} categoryId={categoryId} setCategoryId={setCategoryId} onBack={onExit} onDone={onDone} />;
}

function LookingPostCreation({ city, categories, csrfToken, categoryId, setCategoryId, onBack, onDone }: { city: MapCity | null; categories: Category[]; csrfToken: string; categoryId: string; setCategoryId: (id: string) => void; onBack: () => void; onDone: () => void }) {
  const [title, setTitle] = useState(""); const [body, setBody] = useState(""); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const requestKey = useRef<string | null>(null);
  const save = async () => { if (!city || !categoryId) { setError("Выберите город и категорию."); return; } setSaving(true); setError(""); const key = requestKey.current ?? crypto.randomUUID(); requestKey.current = key; const r = await fetch(`${appConfig.apiBaseUrl}/looking-posts`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, "Idempotency-Key": key }, body: JSON.stringify({ city_id: city.id, category_id: categoryId, title, body }) }); setSaving(false); if (r.ok) { requestKey.current = null; onDone(); } else setError(r.status === 503 ? "Защита от спама временно недоступна. Повторите позже." : "Не удалось опубликовать идею."); };
  return <section className="demo-form"><button className="text-back" type="button" onClick={onBack}>← Назад</button><p className="section-kicker">Ищу людей · 72 часа</p><h1>Новая идея</h1><p className="selected-city"><MapPin /><span><small>Город</small>{city?.name ?? "Выберите город"}</span></p><label>Название<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={30} placeholder="Кого и для чего вы ищете" /></label><label>Категория<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="" disabled>Выберите категорию</option>{categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}</select></label><label>Описание<textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Расскажите самое важное" maxLength={300} /></label>{error && <p className="form-error" role="alert">{error}</p>}<Button disabled={saving || !title.trim() || !body.trim() || !categoryId} onClick={() => void save()}>{saving ? "Публикуем…" : "Опубликовать идею"}</Button></section>;
}

function Notifications({ onUnreadChange }: { onUnreadChange: (count: number) => void }) {
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  useEffect(() => { void fetch(`${appConfig.apiBaseUrl}/account/notifications`, { credentials: "include" }).then(async (response) => response.ok ? await response.json() as NotificationItem[] : []).then((nextItems) => { setItems(nextItems); onUnreadChange(nextItems.filter((item) => !item.read_at).length); }); }, [onUnreadChange]);
  const unread = items?.filter((item) => !item.read_at).length ?? 0;
  const urgentItems = items?.filter((item) => item.importance === "critical") ?? [];
  const regularItems = items?.filter((item) => item.importance !== "critical") ?? [];
  return <section className="feed notifications-screen"><div className="section-heading"><div><p className="section-kicker">Важное и новое</p><h1>Уведомления</h1></div>{unread > 0 && <span className="unread-count">{unread} новых</span>}</div>{items === null ? <TextBlink className="text-blink">Собираем новости…</TextBlink> : items.length ? <>{urgentItems.length > 0 && <NotificationGroup title="Нужно сделать" items={urgentItems} />}{regularItems.length > 0 && <NotificationGroup title="Сегодня" items={regularItems} />}</> : <DecorativeEmpty title="Пока всё спокойно" text="Здесь появятся важные новости о событиях и встречах." />}</section>;
}

function NotificationGroup({ title, items }: { title: string; items: NotificationItem[] }) {
  const headingId = title === "Нужно сделать" ? "notification-action" : "notification-today";
  return <section className="notification-group" aria-labelledby={headingId}><h2 id={headingId}>{title}</h2>{items.map((item) => <Notification key={item.id} icon={<Bell />} title={item.title} text={item.body} urgent={item.importance === "critical"} />)}</section>;
}

function Notification({ icon, title, text, urgent = false }: { icon: React.ReactNode; title: string; text: string; urgent?: boolean }) {
  return <article className={`notification${urgent ? " urgent" : ""}`}><span>{icon}</span><div><strong>{title}</strong><p>{text}</p></div><ChevronRight /></article>;
}

function Profile({
  profile,
  city,
  onChooseCity,
  initialPublicId,
  csrfToken,
  onUpdate,
  onLogout,
  onPreview,
}: { profile: AccountProfile; city: MapCity | null; onChooseCity: () => void; initialPublicId: string | null; csrfToken: string; onUpdate: (profile: AccountProfile) => void; onLogout: () => Promise<void>; onPreview: (state: PreviewState) => void }) {
  const color = `hsl(${Number(profile.public_id.slice(-3)) % 360} 42% 42%)`;
  const [editing, setEditing] = useState(false);
  const [publicProfile, setPublicProfile] = useState<AccountProfile | null>(null);
  const [message, setMessage] = useState("");
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [eventMode, setEventMode] = useState<"upcoming" | "completed" | null>(null);
  const upload = async (file: Blob) => {
    if (avatarBusy) return;
    setMessage("");
    setAvatarBusy(true);
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/account/avatar`, { method: "PUT", credentials: "include", headers: { "Content-Type": file.type, "X-Afisha-CSRF": csrfToken }, body: file });
      if (response.ok) onUpdate(await response.json() as AccountProfile);
      else setMessage(response.status === 413 ? "Фото слишком большое — максимум 12 МБ." : "Не удалось обработать фотографию");
    } catch {
      setMessage("Нет связи с сервером.");
    } finally {
      setAvatarBusy(false);
    }
  };
  const removeAvatar = async () => {
    if (avatarBusy) return;
    const response = await fetch(`${appConfig.apiBaseUrl}/account/avatar`, { method: "DELETE", credentials: "include", headers: { "X-Afisha-CSRF": csrfToken } });
    if (response.ok) onUpdate(await response.json() as AccountProfile);
    else setMessage("Не удалось удалить фотографию");
  };
  useEffect(() => { if (!initialPublicId) return; void fetch(`${appConfig.apiBaseUrl}/profiles/${initialPublicId}`, { credentials: "include" }).then(async (response) => { if (response.ok) setPublicProfile(await response.json() as AccountProfile); else setMessage("Профиль не найден"); }); }, [initialPublicId]);
  if (publicProfile) return <PublicProfile profile={publicProfile} csrfToken={csrfToken} onBack={() => { setPublicProfile(null); window.history.pushState({}, "", "/app"); }} />;
  if (editing) return <ProfileEditor profile={profile} csrfToken={csrfToken} onUpdate={onUpdate} onDone={() => { setEditing(false); setMessage("Профиль сохранён"); }} onBack={() => setEditing(false)} />;
  if (eventMode) return <AccountEvents state={eventMode} csrfToken={csrfToken} onBack={() => setEventMode(null)} />;
  return <section className="profile-screen premium-profile">
    <div className="profile-hero" role="img" aria-label="Горный аул Дагестана на закате"><span className="ornament-divider" aria-hidden="true" /></div>
    <div className="profile-content">
      <div className="profile-identity">
        {profile.avatar_url ? <img className="profile-avatar profile-photo" src={profile.avatar_url} alt="Ваш аватар" /> : <span className="profile-avatar" style={{ backgroundColor: color }}>{profile.display_name[0]}</span>}
        <div><p className="section-kicker">Ваш профиль</p><h1>{profile.display_name}</h1><p><button className="copy-id" type="button" aria-label={`Скопировать ID ${profile.public_id}`} onClick={() => void navigator.clipboard.writeText(profile.public_id)}>ID {profile.public_id}</button> · {profile.organizer_status === "trusted" ? "Доверенный организатор" : "Новый организатор"}</p></div>
      </div>
      <div className="profile-stats" aria-label="Статистика профиля"><div><strong>{profile.upcoming_count ?? 0}</strong><span>будущих</span></div><div><strong>{profile.completed_count ?? 0}</strong><span>завершено</span></div><div><strong>{profile.successful_events ?? 0}</strong><span>успешных</span></div></div>
      <p className="profile-bio">{profile.bio || "Добавьте пару слов о себе — так людям проще решиться на встречу."}</p>
      <Button className="profile-edit-primary" onClick={() => setEditing(true)}>Редактировать профиль</Button>
      {message && <p className="success-message" role="status">{message}</p>}

      <h2 className="group-title">Город и настройки</h2>
      <div className="profile-settings-group">
        <button className="settings-row" type="button" onClick={onChooseCity}><span className="settings-icon city-settings-icon"><MapPin aria-hidden="true" /></span><span><small>Мой город</small><strong>{city?.name ?? "Выберите город"}</strong></span><ChevronRight aria-hidden="true" /></button>
        <label className="settings-row file-settings-row"><span className="settings-icon"><ImageOff aria-hidden="true" /></span><span><small>Фотография</small><strong>{avatarBusy ? "Загружаем…" : profile.avatar_url ? "Заменить фотографию" : "Добавить фотографию"}</strong></span><ChevronRight aria-hidden="true" /><input type="file" accept="image/jpeg,image/png,image/webp" disabled={avatarBusy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} /></label>
        {profile.avatar_url && <button className="settings-row danger-settings-row" type="button" disabled={avatarBusy} onClick={() => void removeAvatar()}><span>Удалить фотографию</span><ChevronRight aria-hidden="true" /></button>}
      </div>

      <h2 className="group-title">Моя активность</h2>
      <div className="profile-settings-group"><button className="settings-row" type="button" onClick={() => setEventMode("upcoming")}><span><small>События</small><strong>Будущие события</strong></span><ChevronRight aria-hidden="true" /></button><button className="settings-row" type="button" onClick={() => setEventMode("completed")}><span><small>История</small><strong>Завершённые события</strong></span><ChevronRight aria-hidden="true" /></button></div>

      <Button className="logout-button" variant="outline" onClick={() => void onLogout()}>Выйти из аккаунта</Button>
      {import.meta.env.DEV && <><h2 className="group-title">Предпросмотр состояний</h2><div className="state-buttons"><Button variant="outline" onClick={() => onPreview("loading")}>Загрузка</Button><Button variant="outline" onClick={() => onPreview("empty")}>Пусто</Button><Button variant="outline" onClick={() => onPreview("error")}>Ошибка</Button></div></>}
    </div>
  </section>;
}

function ProfileEditor({ profile, csrfToken, onUpdate, onDone, onBack }: { profile: AccountProfile; csrfToken: string; onUpdate: (profile: AccountProfile) => void; onDone: () => void; onBack: () => void }) {
  const [name, setName] = useState(profile.display_name);
  const [bio, setBio] = useState(profile.bio ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const save = async () => {
    setSaving(true);
    setMessage("");
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/account/profile`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken }, body: JSON.stringify({ display_name: name, bio, selected_city_id: profile.selected_city_id, version: profile.version ?? 1 }) });
      if (response.ok) { onUpdate(await response.json() as AccountProfile); onDone(); }
      else setMessage(response.status === 409 ? "Псевдоним можно менять раз в 7 дней" : "Не удалось сохранить профиль");
    } catch {
      setMessage("Нет связи с сервером.");
    } finally {
      setSaving(false);
    }
  };
  return <section className="feed profile-screen"><button className="text-back" type="button" onClick={onBack}>← Назад</button><p className="section-kicker">Профиль</p><h1>Редактировать профиль</h1><div className="profile-editor"><label>Псевдоним<input value={name} onChange={(event) => setName(event.target.value)} maxLength={32} /></label><label>О себе<textarea value={bio} onChange={(event) => setBio(event.target.value)} maxLength={150} /></label></div>{message && <p className="form-error" role="alert">{message}</p>}<Button disabled={saving || !name.trim()} onClick={() => void save()}>{saving ? "Сохраняем…" : "Сохранить"}</Button></section>;
}


function AccountEvents({ state, csrfToken, onBack }: { state: "upcoming" | "completed"; csrfToken: string; onBack: () => void }) {
  const [items, setItems] = useState<ProfileEvent[] | null>(null);
  const [managedEvent, setManagedEvent] = useState<string | null>(null);
  useEffect(() => { void fetch(`${appConfig.apiBaseUrl}/account/events?state=${state}&limit=20`, { credentials: "include" }).then(async (response) => setItems(response.ok ? ((await response.json()) as { items: ProfileEvent[] }).items : [])); }, [state]);
  if (managedEvent) return <EventManagement eventId={managedEvent} csrfToken={csrfToken} onBack={() => setManagedEvent(null)} />;
  return <section className="feed"><button className="text-back" type="button" onClick={onBack}>← Назад</button><h1>{state === "upcoming" ? "Будущие события" : "Завершённые события"}</h1>{items === null ? <p>Загружаем…</p> : items.length ? items.map((event) => <article className="profile-event" key={event.id}><strong>{event.title}</strong><span>{event.role === "organizer" ? "Вы организатор" : "Вы участник"} · {event.category}</span>{state === "upcoming" && event.role === "organizer" && <Button variant="outline" onClick={() => setManagedEvent(event.id)}>Управление</Button>}</article>) : <p>Здесь пока пусто.</p>}</section>;
}

function PublicProfile({ profile, csrfToken, onBack }: { profile: AccountProfile; csrfToken: string; onBack: () => void }) {
  const [reason, setReason] = useState("photo"); const [comment, setComment] = useState(""); const [sent, setSent] = useState(false);
  const [upcoming, setUpcoming] = useState<ProfileEvent[]>([]); const [completed, setCompleted] = useState<ProfileEvent[]>([]); const [nextCompleted, setNextCompleted] = useState<number | null>(null);
  useEffect(() => { void Promise.all([fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/events?state=upcoming&limit=20`, { credentials: "include" }), fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/events?state=completed&limit=10`, { credentials: "include" })]).then(async ([future, history]) => { if (future.ok) setUpcoming(((await future.json()) as { items: ProfileEvent[] }).items); if (history.ok) { const data = await history.json() as { items: ProfileEvent[]; next_offset: number | null }; setCompleted(data.items); setNextCompleted(data.next_offset); } }); }, [profile.public_id]);
  const loadMore = async () => { if (nextCompleted === null) return; const response = await fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/events?state=completed&limit=10&offset=${nextCompleted}`, { credentials: "include" }); if (response.ok) { const data = await response.json() as { items: ProfileEvent[]; next_offset: number | null }; setCompleted((items) => [...items, ...data.items]); setNextCompleted(data.next_offset); } };
  const report = async () => { const response = await fetch(`${appConfig.apiBaseUrl}/profiles/${profile.public_id}/reports`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken }, body: JSON.stringify({ reason, comment: comment || null }) }); if (response.ok) setSent(true); };
  return <section className="feed profile-screen"><button className="text-back" type="button" onClick={onBack}>← Назад</button><div className="profile-card">{profile.avatar_url ? <img className="profile-avatar profile-photo" src={profile.avatar_url} alt="Аватар пользователя" /> : <span className="profile-avatar">{profile.display_name[0]}</span>}<div><p className="section-kicker">Публичный профиль</p><h1>{profile.display_name}</h1><p>ID {profile.public_id} · {profile.organizer_status === "trusted" ? "Доверенный организатор" : "Новый организатор"}</p></div></div><p className="profile-bio">{profile.bio || "Описание не заполнено"}</p><h2 className="group-title">Будущие события</h2>{upcoming.length ? upcoming.map((event) => <article className="profile-event" key={event.id}><strong>{event.title}</strong><span>{event.category} · {new Date(event.starts_at).toLocaleDateString("ru-RU")}</span></article>) : <p className="state-hint">Опубликованных событий пока нет.</p>}<h2 className="group-title">Завершённые события</h2>{completed.length ? completed.map((event) => <article className="profile-event" key={event.id}><strong>{event.title}</strong><span>{event.category} · {new Date(event.ends_at).toLocaleDateString("ru-RU")}</span></article>) : <p className="state-hint">История пока пуста.</p>}{nextCompleted !== null && <Button variant="outline" onClick={() => void loadMore()}>Загрузить ещё</Button>}<h2 className="group-title">Пожаловаться на профиль</h2>{sent ? <p className="success-message">Жалоба отправлена</p> : <div className="profile-editor"><select value={reason} onChange={(event) => setReason(event.target.value)}><option value="photo">Фотография</option><option value="display_name">Псевдоним</option><option value="bio">Описание</option><option value="other">Другое</option></select>{reason === "other" && <textarea maxLength={300} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Опишите причину" />}<Button disabled={reason === "other" && !comment.trim()} onClick={() => void report()}>Отправить жалобу</Button></div>}</section>;
}

function StreetGroupSheet({ group, onClose, onOpen }: { group: { ids: string[]; street: string }; onClose: () => void; onOpen: (id: string) => void }) {
  const [items, setItems] = useState<PublicEvent[] | null>(null);
  useEffect(() => {
    void Promise.all(group.ids.map(async (id) => {
      const response = await fetch(`${appConfig.apiBaseUrl}/events/${id}`, { credentials: "include" });
      if (!response.ok) return null;
      return await response.json() as PublicEvent;
    })).then((events) => setItems(events.filter((item): item is PublicEvent => item !== null)));
  }, [group.ids]);
  return <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}><SheetContent className="street-group-sheet"><p className="section-kicker">Общая улица</p><SheetTitle>{group.street}</SheetTitle><SheetDescription>Метка не показывает примерное место конкретного события.</SheetDescription>{items === null ? <div className="sheet-list-skeleton" aria-label="Загружаем события"><span /><span /></div> : items.map((item) => <button className="street-group-event" type="button" key={item.id} onClick={() => onOpen(item.id)}><EventPhoto src={item.photo_url} alt="" /><span><strong>{item.title}</strong><small>{formatEventTime(item.starts_at)} · {item.category}</small></span><ChevronRight aria-hidden="true" /></button>)}</SheetContent></Sheet>;
}

function EventPage({ eventId, csrfToken, onClose, onOpenChat }: { eventId: string; csrfToken: string; onClose: () => void; onOpenChat: () => void }) {
  const [event, setEvent] = useState<PublicEvent | null>(null);
  const [failed, setFailed] = useState(false);
  const [organizer, setOrganizer] = useState<AccountProfile | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [managing, setManaging] = useState(false);
  useEffect(() => {
    setEvent(null); setFailed(false);
    void fetch(`${appConfig.apiBaseUrl}/events/${eventId}`, { credentials: "include" })
      .then(async (response) => { if (!response.ok) throw new Error(); return await response.json() as PublicEvent; })
      .then(setEvent).catch(() => setFailed(true));
  }, [eventId]);
  const openOrganizer = async () => {
    if (!event?.organizer_public_id) return;
    const response = await fetch(`${appConfig.apiBaseUrl}/profiles/${event.organizer_public_id}`);
    if (response.ok) setOrganizer(await response.json() as AccountProfile);
  };
  const share = async () => {
    const url = `${window.location.origin}/event/${eventId}`;
    if (navigator.share) await navigator.share({ title: event?.title, url }).catch(() => undefined);
    else { await navigator.clipboard.writeText(url); setCopied(true); }
  };
  const reload = async () => {
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}`, { credentials: "include" });
    if (response.ok) setEvent(await response.json() as PublicEvent);
  };
  const toggleInterest = async () => {
    if (!event || busy) return;
    setBusy(true); setMessage("");
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/interest`, {
      method: event.viewer_interested ? "DELETE" : "PUT", credentials: "include",
      headers: { "X-Afisha-CSRF": csrfToken },
    });
    setBusy(false);
    if (response.ok) {
      const result = await response.json() as { interested: boolean; interest_count: number };
      setEvent({ ...event, viewer_interested: result.interested, interest_count: result.interest_count });
    } else setMessage("Не удалось сохранить отметку.");
  };
  const join = async () => {
    if (!event || busy) return;
    setBusy(true); setMessage("");
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/join`, {
      method: "POST", credentials: "include", headers: { "X-Afisha-CSRF": csrfToken },
    });
    setBusy(false);
    if (response.ok) {
      const result = await response.json() as { state: "participating" | "waitlisted"; queue_position: number | null };
      setMessage(result.state === "participating" ? "Вы стали участником." : `Вы в очереди под номером ${result.queue_position}.`);
      await reload();
    } else {
      const data = await response.json().catch(() => null) as { detail?: string } | null;
      setMessage(data?.detail === "participant_excluded" ? "Организатор ранее исключил вас из этого события." : "Не удалось вступить в событие.");
    }
  };
  const leave = async () => {
    if (!event || busy) return;
    if (new Date(event.starts_at) <= new Date() && !await confirmEventLeave()) return;
    setBusy(true); setMessage("");
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/leave`, {
      method: "POST", credentials: "include", headers: { "X-Afisha-CSRF": csrfToken },
    });
    setBusy(false);
    if (response.ok) { setMessage("Вы больше не участвуете в событии."); await reload(); }
    else setMessage("Не удалось выйти из события.");
  };
  if (organizer) return <section className="feed page-screen event-page"><button className="text-back" type="button" onClick={() => setOrganizer(null)}>← К событию</button><PublicOrganizer profile={organizer} /></section>;
  if (managing) return <section className="feed page-screen event-page"><EventManagement eventId={eventId} csrfToken={csrfToken} onBack={() => { setManaging(false); void reload(); }} /></section>;
  const canChat = Boolean(event?.kind === "regular" && event.lifecycle_status === "published" && (event.viewer_is_organizer || event.viewer_membership === "participating") && event.chat_enabled);
  const showPrimaryAction = Boolean(event?.kind === "regular" && event.lifecycle_status === "published" && (event.viewer_is_organizer || event.viewer_membership === "none" || event.viewer_membership === "participating" || event.viewer_membership === "waitlisted"));
  return <section className={`event-detail-page${event ? ` category-${event.category_slug}` : ""}`}>
    <header className="event-detail-appbar"><button type="button" aria-label="Назад" onClick={onClose}><ArrowLeft aria-hidden="true" /></button><strong>Событие</strong><span>{canChat && <button type="button" aria-label="Открыть чат события" onClick={onOpenChat}><MessageCircleQuestion aria-hidden="true" /></button>}<button type="button" aria-label="Поделиться событием" onClick={() => void share()}><Share2 aria-hidden="true" /></button></span></header>
    {failed ? <DemoState state="error" onClose={onClose} /> : !event ? <DemoState state="loading" /> : <><div className="event-detail-scroll"><EventPhoto className="event-detail-hero" src={event.photo_url} alt={`Фотография события «${event.title}»`} /><main className="event-detail-content">
      <div className="event-detail-labels"><span className="category-chip">{event.category}</span>{event.kind === "special" && <span className="municipal-label"><Sparkles aria-hidden="true" /> Общественное</span>}<button className={`interest-button${event.viewer_interested ? " active" : ""}`} type="button" aria-label={`${event.viewer_interested ? "Убрать из интересного" : "Добавить в интересное"}. Всего ${event.interest_count ?? 0}`} aria-pressed={event.viewer_interested} disabled={busy || event.lifecycle_status !== "published"} onClick={() => void toggleInterest()}><Heart aria-hidden="true" /> {event.interest_count ?? 0}</button></div>
      <h1>{event.title}</h1>
      <div className="event-facts"><div><span><CalendarDays aria-hidden="true" /></span><p><small>Когда</small><strong>{formatEventTime(event.starts_at)}</strong><span>до {formatEventTime(event.ends_at)}</span></p></div><div><span><MapPin aria-hidden="true" /></span><p><small>Где</small><strong>{event.visible_address}</strong></p></div><div><span><Users aria-hidden="true" /></span><p><small>Участники</small><strong>{event.participant_count} собираются</strong><span>{event.capacity === null ? "Без ограничения мест" : `Свободно: ${event.available_places}`}</span></p></div></div>
      {event.lifecycle_status === "cancelled" && <p className="event-state danger">Событие отменено</p>}
      {event.viewer_membership === "waitlisted" && <p className="event-state info">Вы в очереди · №{event.queue_position}</p>}
      {event.viewer_membership === "participating" && <p className="event-state success"><Check aria-hidden="true" />Вы участвуете. Точный адрес доступен по правилам события.</p>}
      {event.viewer_membership === "excluded" && <p className="event-state danger">Организатор завершил ваше участие. Повторное вступление недоступно.</p>}
      <section className="event-about"><h2>О событии</h2><p>{event.description}</p></section>
      {event.kind === "regular" ? <button className="organizer-link" type="button" onClick={() => void openOrganizer()}><span className="demo-avatar">{event.organizer_name?.[0] ?? "?"}</span><span><small>Организатор</small><strong>{event.organizer_name}</strong><small>{event.organizer_status === "trusted" ? "Доверенный организатор" : "Новый организатор"}</small></span><ChevronRight aria-hidden="true" /></button> : <div className="municipal-organizer"><Sparkles aria-hidden="true" /><span><small>Организатор отсутствует</small><strong>Общественное событие</strong></span></div>}
      {message && <p className="inline-feedback" role="status">{message}</p>}{copied && <p className="inline-feedback" role="status">Ссылка скопирована</p>}
    </main></div>
    {showPrimaryAction && <footer className="event-sticky-cta">{event.viewer_is_organizer ? <Button onClick={() => setManaging(true)}>Управлять событием</Button> : event.viewer_membership === "none" ? <Button disabled={busy} onClick={() => void join()}>{event.capacity !== null && event.available_places === 0 ? "Встать в очередь" : "Присоединиться"}</Button> : event.viewer_membership === "participating" ? <Button variant="outline" disabled={busy} onClick={() => void leave()}>Отказаться от участия</Button> : event.viewer_membership === "waitlisted" ? <Button variant="outline" disabled={busy} onClick={() => void leave()}>Покинуть очередь</Button> : null}</footer>}</>}
  </section>;
}

async function confirmEventLeave(): Promise<boolean> {
  const text = "Событие уже началось. Выйти из участников? Освободившееся место сразу получит первый человек в очереди.";
  const webApp = window.Telegram?.WebApp;
  if (webApp?.showConfirm) return await new Promise<boolean>((resolve) => webApp.showConfirm?.(text, resolve));
  return window.confirm(text);
}

function PublicOrganizer({ profile }: { profile: AccountProfile }) {
  return <div className="public-organizer-card">{profile.avatar_url ? <img className="profile-avatar profile-photo" src={profile.avatar_url} alt="Аватар организатора" /> : <span className="profile-avatar">{profile.display_name[0]}</span>}<p className="section-kicker">Организатор</p><h1>{profile.display_name}</h1><p>{profile.organizer_status === "trusted" ? "Доверенный организатор" : "Новый организатор"}</p><p className="profile-bio">{profile.bio || "Описание пока не заполнено"}</p></div>;
}

function formatEventTime(value: string): string {
  return new Date(value).toLocaleString("ru-RU", { timeZone: "Europe/Moscow", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function DecorativeEmpty({ title, text }: { title: string; text: string }) {
  return <div className="decorative-empty" role="status"><span className="empty-landscape" aria-hidden="true"><i /><i /><i /></span><span className="ornament-divider" aria-hidden="true" /><h2>{title}</h2><p>{text}</p></div>;
}

function DemoState({ state, onClose }: { state: Exclude<PreviewState, null>; onClose?: () => void }) {
  const content = { loading: { icon: <LoaderCircle className="spin" />, title: "Загружаем", text: "Секунду, собираем всё самое интересное." }, empty: { icon: <SearchX />, title: "Здесь пока пусто", text: "Можно создать первую встречу или посмотреть, кто ищет компанию." }, error: { icon: <RefreshCw />, title: "Не получилось загрузить", text: "Проверьте связь и попробуйте ещё раз. Ваши действия не потерялись." } }[state];
  if (state === "loading") return <section className="skeleton-screen" role="status" aria-label="Загружаем"><TextBlink className="text-blink">Собираем события…</TextBlink><div className="skeleton-hero" /><div className="skeleton-lines"><span /><span /><span /></div><div className="skeleton-card" /><span className="sr-only">Загружаем содержимое</span></section>;
  return <section className="centered-screen state-screen" role={state === "error" ? "alert" : "status"}>{onClose && <button className="state-close" type="button" aria-label="Закрыть пример" onClick={onClose}><X /></button>}<span className="big-icon">{content.icon}</span><h1>{content.title}</h1><p>{content.text}</p>{state === "error" && <Button onClick={onClose}><RefreshCw /> Повторить</Button>}{state === "empty" && <Button onClick={onClose}><Plus /> Создать первую идею</Button>}</section>;
}

async function confirmFormLoss(): Promise<boolean> {
  const webApp = window.Telegram?.WebApp;
  if (webApp?.showConfirm) {
    return await new Promise<boolean>((resolve) => webApp.showConfirm?.(
      "Закрыть форму? Введённые данные не сохранятся.",
      resolve,
    ));
  }
  return window.confirm("Закрыть форму? Введённые данные не сохранятся.");
}
