import { CheckCircle2, MapPin, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { appConfig } from "@/config";
import { EventMap, type MapCity, type ResolvedLocation } from "@/components/event-map";
import { EventPhotoUploader, type EventPhotoUpload } from "@/components/photo-cropper";
import { Button } from "@/components/ui/button";

type AddressVisibility = "exact_public" | "exact_participants" | "street_only";
type OrganizerStatus = "new" | "trusted";

interface Category {
  id: string;
  name: string;
  is_special: boolean;
  organizer_selectable: boolean;
}

interface EventCreationProps {
  city: MapCity;
  categories: Category[];
  csrfToken: string;
  organizerStatus: OrganizerStatus;
  onDirtyChange: (dirty: boolean) => void;
  registerDiscard: (discard: (() => Promise<void>) | null) => void;
  onChooseCity: () => void;
  onCancel: () => void;
  onFinished: () => void;
}

interface SubmittedEvent {
  event_id: string;
  status: "published" | "pending_review";
}

export function EventCreation({ city, categories, csrfToken, organizerStatus, onDirtyChange, registerDiscard, onChooseCity, onCancel, onFinished }: EventCreationProps) {
  const [step, setStep] = useState(1);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [limited, setLimited] = useState(false);
  const [capacity, setCapacity] = useState("3");
  const [location, setLocation] = useState<ResolvedLocation | null>(null);
  const [addressText, setAddressText] = useState("");
  const [locationNote, setLocationNote] = useState("");
  const [visibility, setVisibility] = useState<AddressVisibility>("exact_public");
  const [photo, setPhoto] = useState<EventPhotoUpload | null>(null);
  const [addressConfirmed, setAddressConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState<SubmittedEvent | null>(null);
  const submissionRef = useRef<{ payload: string; key: string } | null>(null);
  const handleLocationChange = useCallback((value: ResolvedLocation | null) => {
    submissionRef.current = null;
    setError("");
    setLocation(value);
    setAddressText(value?.display_name ?? "");
    setLocationNote("");
    setAddressConfirmed(false);
  }, []);

  const selectableCategories = useMemo(
    () => categories.filter((category) => category.organizer_selectable && !category.is_special),
    [categories],
  );
  const dirty = Boolean(title || description || categoryId || startsAt || endsAt || location || addressText || locationNote || photo || limited);

  const discard = useCallback(async () => {
    if (photo) {
      await fetch(`${appConfig.apiBaseUrl}/media/event-photos/${photo.upload_id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-Afisha-CSRF": csrfToken },
      }).catch(() => undefined);
    }
    onDirtyChange(false);
  }, [csrfToken, onDirtyChange, photo]);

  useEffect(() => {
    onDirtyChange(dirty && !submitted);
    registerDiscard(discard);
    return () => registerDiscard(null);
  }, [dirty, discard, onDirtyChange, registerDiscard, submitted]);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (dirty && !submitted) webApp?.enableClosingConfirmation?.();
    else webApp?.disableClosingConfirmation?.();
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty || submitted) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      webApp?.disableClosingConfirmation?.();
    };
  }, [dirty, submitted]);

  useEffect(() => {
    setLocation(null);
    setAddressText("");
    setLocationNote("");
    setStep((current) => Math.min(current, 3));
  }, [city.id]);

  useEffect(() => {
    setAddressConfirmed(false);
  }, [location, visibility, addressText]);

  const change = <T,>(setter: (value: T) => void, value: T) => {
    submissionRef.current = null;
    setError("");
    setter(value);
  };

  const validateStep = (current: number): string | null => {
    if (current === 1) {
      if (!title.trim()) return "Введите название события.";
      if (title.trim().length > 60) return "Название должно быть не длиннее 60 символов.";
      if (!categoryId) return "Выберите категорию.";
      if (!description.trim()) return "Добавьте описание события.";
    }
    if (current === 2) {
      if (!startsAt || !endsAt) return "Укажите начало и окончание события.";
      const start = moscowDate(startsAt);
      const end = moscowDate(endsAt);
      if (!start || !end) return "Проверьте дату и время.";
      const minimumHours = organizerStatus === "trusted" ? 1 : 6;
      if (start.getTime() < Date.now() + minimumHours * 60 * 60 * 1000) return `Начало должно быть минимум через ${minimumHours === 1 ? "1 час" : "6 часов"}.`;
      if (end <= start) return "Окончание должно быть позже начала.";
      if (end.getTime() - start.getTime() > 7 * 24 * 60 * 60 * 1000) return "Событие не может длиться больше 7 суток.";
      if (limited && Number(capacity) < 3) return "Минимальный лимит — 3 участника.";
    }
    if (current === 3) {
      if (!location) return "Выберите и подтвердите место внутри города.";
    }
    if (current === 4) {
      if (!location || (!location.street && visibility !== "exact_public")) return "Без определённой улицы доступен только публичный точный адрес.";
      if (!addressText.trim()) return "Проверьте и укажите адрес для карточки.";
      if (location.precision === "locality" && visibility === "exact_public" && addressText.trim() === location.display_name) return "Добавьте улицу, дом или ориентир к адресу.";
      if (!addressConfirmed) return "Подтвердите, что вы проверили адрес.";
    }
    if (current === 5 && !photo) return "Добавьте фотографию события.";
    return null;
  };

  const goNext = () => {
    const problem = validateStep(step);
    if (problem) { setError(problem); return; }
    window.Telegram?.WebApp?.hideKeyboard?.();
    (document.activeElement as HTMLElement | null)?.blur?.();
    setError("");
    setStep((current) => Math.min(current + 1, 5));
  };

  const requestCancel = async () => {
    if (!dirty) { onCancel(); return; }
    if (!await confirmLoss()) return;
    await discard();
    onCancel();
  };

  const submit = async () => {
    const problem = [1, 2, 3, 4, 5].map(validateStep).find(Boolean);
    if (problem || !location || !photo) { setError(problem ?? "Заполните форму."); return; }
    window.Telegram?.WebApp?.hideKeyboard?.();
    (document.activeElement as HTMLElement | null)?.blur?.();
    const payload = JSON.stringify({
      title: title.trim(), description: description.trim(), category_id: categoryId,
      city_id: city.id, starts_at: moscowDate(startsAt)?.toISOString(), ends_at: moscowDate(endsAt)?.toISOString(),
      capacity: limited ? Number(capacity) : null, latitude: location.latitude, longitude: location.longitude,
      address_visibility: visibility, address_text: addressText.trim(), address_confirmed: addressConfirmed,
      location_note: locationNote.trim() || null,
      photo_upload_id: photo.upload_id,
    });
    const requestIdentity = submissionRef.current?.payload === payload
      ? submissionRef.current
      : { payload, key: crypto.randomUUID() };
    submissionRef.current = requestIdentity;
    setBusy(true); setError("");
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/events`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, "Idempotency-Key": requestIdentity.key },
        body: payload,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { detail?: string } | null;
        throw new EventSubmitError(response.status, body?.detail);
      }
      setSubmitted(await response.json() as SubmittedEvent);
      onDirtyChange(false);
    } catch (reason) {
      setError(eventErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  if (submitted) return <section className="event-submit-success"><CheckCircle2 /><p className="section-kicker">Событие создано</p><h1>{submitted.status === "published" ? "Опубликовано" : "Отправлено на проверку"}</h1><p>{submitted.status === "published" ? "Событие уже доступно пользователям." : "До решения проверки событие не будет видно другим пользователям."}</p><Button onClick={onFinished}>Вернуться к событиям</Button></section>;

  const category = selectableCategories.find((item) => item.id === categoryId);
  return <section className="event-wizard"><header className="event-wizard-header"><button className="text-back" type="button" onClick={() => void requestCancel()}>← Закрыть</button><span>Шаг {step} из 5</span></header><div className="wizard-progress" aria-label={`Шаг ${step} из 5`}>{[1, 2, 3, 4, 5].map((number) => <button type="button" key={number} className={number <= step ? "active" : ""} disabled={number >= step} onClick={() => setStep(number)}>{number}</button>)}</div><div className="wizard-body scroll-focus-container">{step === 1 && <section className="wizard-step"><p className="section-kicker">Основное</p><h1>Расскажите о событии</h1><label>Название<input value={title} maxLength={60} onChange={(event) => change(setTitle, event.target.value)} placeholder="Например, прогулка у моря" /><small>{title.length}/60</small></label><label>Категория<select value={categoryId} onChange={(event) => change(setCategoryId, event.target.value)}><option value="" disabled>Выберите категорию</option>{selectableCategories.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label>Описание<textarea value={description} maxLength={1000} onChange={(event) => change(setDescription, event.target.value)} placeholder="Что будет происходить и что важно знать участникам" /><small>{description.length}/1000</small></label></section>}{step === 2 && <section className="wizard-step"><p className="section-kicker">Время и участие</p><h1>Когда встречаемся?</h1><label>Начало<input type="datetime-local" value={startsAt} min={minimumLocalDate(organizerStatus === "trusted" ? 1 : 6)} onChange={(event) => change(setStartsAt, event.target.value)} /></label><label>Окончание<input type="datetime-local" value={endsAt} min={startsAt} onChange={(event) => change(setEndsAt, event.target.value)} /></label><label className="capacity-toggle"><input type="checkbox" checked={limited} onChange={(event) => change(setLimited, event.target.checked)} /><span><strong>Ограничить количество мест</strong><small>Организатор не входит в лимит.</small></span></label>{limited && <label>Количество участников<input type="number" min="3" inputMode="numeric" value={capacity} onChange={(event) => change(setCapacity, event.target.value)} /></label>}</section>}{step === 3 && <section className="wizard-step wizard-map-step"><div className="wizard-map-heading"><div><p className="section-kicker">Место</p><h1>Выберите место</h1></div><button className="selected-city compact" type="button" onClick={onChooseCity}><MapPin /><span>{city.name}</span></button></div><EventMap embedded selecting city={city} onLocationChange={handleLocationChange} /></section>}{step === 4 && <section className="wizard-step"><p className="section-kicker">Адрес</p><h1>Проверьте адрес</h1><label>Адрес для карточки<input value={addressText} maxLength={300} onChange={(event) => change(setAddressText, event.target.value)} placeholder="Улица, дом, ориентир" /><small>{addressText.length}/300</small></label>{location?.precision === "locality" && <p className="state-hint">Карта нашла только город. Добавьте улицу, дом или ориентир.</p>}<fieldset className="visibility-options"><legend>Видимость</legend><VisibilityOption value="exact_public" selected={visibility} onSelect={(value) => change(setVisibility, value)} title="Видно всем" text="Точное место сразу видно в карточке." /><VisibilityOption value="exact_participants" selected={visibility} onSelect={(value) => change(setVisibility, value)} disabled={Boolean(location && !location.street)} title="Только участникам" text="Остальные увидят только улицу." /><VisibilityOption value="street_only" selected={visibility} onSelect={(value) => change(setVisibility, value)} disabled={Boolean(location && !location.street)} title="Только улица" text="Точное место видно только вам." /></fieldset><label>Дом, вход или ориентир <small>необязательно</small><input value={locationNote} maxLength={80} onChange={(event) => change(setLocationNote, event.target.value)} placeholder="Например: дом 12, у главного входа" /><small>{locationNote.length}/80</small></label><label className="address-confirmation"><input type="checkbox" checked={addressConfirmed} onChange={(event) => setAddressConfirmed(event.target.checked)} /><span><strong>Я проверил адрес — он верный</strong><small>Метка на карте и текст адреса совпадают.</small></span></label></section>}{step === 5 && <section className="wizard-step"><p className="section-kicker">Фотография</p><h1>Фото места</h1><EventPhotoUploader csrfToken={csrfToken} value={photo} onChange={(value) => change(setPhoto, value)} />{photo && <article className="event-preview"><img src={photo.preview_url} alt="Фотография места события" /><div><span className="category-chip">{category?.name}</span><h2>{title}</h2><p>{formatMoscow(startsAt)} — {formatMoscow(endsAt)}</p><p><MapPin /> {addressText}{locationNote ? ` · ${locationNote}` : ""}</p><p><Users /> {limited ? `До ${capacity} участников` : "Без ограничения мест"}</p><p>{description}</p></div></article>}</section>}{error && <p className="form-error wizard-error" role="alert">{error}</p>}</div><footer className="wizard-actions">{step > 1 && <Button variant="outline" disabled={busy} onClick={() => { setError(""); setStep((current) => current - 1); }}>Назад</Button>}{step < 5 ? <Button onClick={goNext}>Продолжить</Button> : <Button disabled={busy || !photo} onClick={() => void submit()}>{busy ? "Отправляем…" : organizerStatus === "trusted" ? "Опубликовать" : "Отправить на проверку"}</Button>}</footer></section>;
}

function VisibilityOption({ value, selected, onSelect, title, text, disabled = false }: { value: AddressVisibility; selected: AddressVisibility; onSelect: (value: AddressVisibility) => void; title: string; text: string; disabled?: boolean }) {
  return <label className="visibility-option"><input type="radio" name="event-address-visibility" value={value} checked={selected === value} disabled={disabled} onChange={() => onSelect(value)} /><span><strong>{title}</strong><small>{text}</small></span></label>;
}

function moscowDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null;
  const date = new Date(`${value}:00+03:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function minimumLocalDate(hours: number): string {
  return new Date(Date.now() + (hours + 3) * 60 * 60 * 1000).toISOString().slice(0, 16);
}

function formatMoscow(value: string): string {
  const date = moscowDate(value);
  return date ? date.toLocaleString("ru-RU", { timeZone: "Europe/Moscow", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }) : "Время не указано";
}

async function confirmLoss(): Promise<boolean> {
  const webApp = window.Telegram?.WebApp;
  if (webApp?.showConfirm) return await new Promise<boolean>((resolve) => webApp.showConfirm?.("Закрыть форму? Введённые данные не сохранятся.", resolve));
  return window.confirm("Закрыть форму? Введённые данные не сохранятся.");
}

class EventSubmitError extends Error {
  constructor(public status: number, public code?: string) { super(code); }
}

function eventErrorMessage(reason: unknown): string {
  if (!(reason instanceof EventSubmitError)) return "Не удалось отправить событие. Проверьте соединение и попробуйте снова.";
  const messages: Record<string, string> = {
    start_too_soon_new: "Для нового организатора начало должно быть минимум через 6 часов.",
    start_too_soon_trusted: "Начало должно быть минимум через 1 час.",
    point_outside_city_area: "Выберите место не дальше 20 км от города.",
    photo_not_available: "Фотография устарела или уже использована. Загрузите её снова.",
    category_not_available: "Эта категория больше недоступна.",
    address_unavailable: "Сейчас не удаётся подтвердить адрес. Попробуйте позже.",
    idempotency_key_reused: "Данные изменились во время отправки. Повторите попытку.",
  };
  return reason.code && messages[reason.code] ? messages[reason.code] : "Проверьте заполненные данные и попробуйте снова.";
}
