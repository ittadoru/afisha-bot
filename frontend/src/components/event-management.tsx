import { CalendarClock, LockKeyhole, MapPin } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { appConfig } from "@/config";
import { EventPhotoUploader, type EventPhotoUpload } from "@/components/photo-cropper";
import { Button } from "@/components/ui/button";
import { LoadingScreen } from "@/components/ui/loading-screen";

type ManagedEvent = {
  id: string;
  lifecycle_status: string;
  schedule_changes_used: number;
  category: string;
  city: string;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  normalized_address: string;
  photo_url: string;
  pending_status: "pending" | "rejected" | null;
  rejection_reason: string | null;
  can_edit: boolean;
  can_change_schedule: boolean;
  can_cancel: boolean;
};

type RosterParticipant = { participation_id: string; public_id: string; display_name: string; joined_at: string };
type RosterWaiter = { public_id: string; display_name: string; queued_at: string; position: number };

const cancelReasons = [
  ["plans_changed", "Планы изменились"],
  ["not_enough_participants", "Не набралось участников"],
  ["venue_problem", "Проблемы с местом"],
  ["unforeseen_circumstances", "Непредвиденные обстоятельства"],
] as const;

export function EventManagement({ eventId, csrfToken, onBack }: { eventId: string; csrfToken: string; onBack: () => void }) {
  const [event, setEvent] = useState<ManagedEvent | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [photo, setPhoto] = useState<EventPhotoUpload | null>(null);
  const [cancelReason, setCancelReason] = useState("plans_changed");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const requestRef = useRef<{ body: string; key: string } | null>(null);

  useEffect(() => {
    void fetch(`${appConfig.apiBaseUrl}/events/${eventId}/manage`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const data = await response.json() as ManagedEvent;
        setEvent(data); setTitle(data.title); setDescription(data.description);
        setStartsAt(toMoscowInput(data.starts_at)); setEndsAt(toMoscowInput(data.ends_at));
      })
      .catch(() => setMessage("Не удалось открыть управление событием."));
  }, [eventId]);

  const submit = async () => {
    if (!event) return;
    const body = JSON.stringify({
      title, description,
      starts_at: fromMoscowInput(startsAt), ends_at: fromMoscowInput(endsAt),
      photo_upload_id: photo?.upload_id ?? null,
    });
    if (!requestRef.current || requestRef.current.body !== body) {
      requestRef.current = { body, key: crypto.randomUUID() };
    }
    setBusy(true); setMessage("");
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/revisions`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, "Idempotency-Key": requestRef.current.key },
      body,
    });
    setBusy(false);
    if (response.ok) {
      setMessage("Изменения отправлены на проверку. Пока видна прежняя версия.");
      setEvent({ ...event, pending_status: "pending", can_edit: false });
    } else {
      const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
      setMessage(detail?.detail === "schedule_change_already_used" ? "Перенос времени уже использован." : "Не удалось отправить изменения.");
    }
  };

  const cancel = async () => {
    if (!await confirmCancel()) return;
    setBusy(true);
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/cancel`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken },
      body: JSON.stringify({ reason: cancelReason }),
    });
    setBusy(false);
    if (response.ok) {
      setMessage("Событие отменено. Участники получили уведомление.");
      if (event) setEvent({ ...event, lifecycle_status: "cancelled", can_edit: false, can_cancel: false });
    } else setMessage("Не удалось отменить событие.");
  };

  if (!event) return <section className="feed"><button className="text-back" onClick={onBack}>← Назад</button>{message ? <p className="form-error" role="alert">{message}</p> : <LoadingScreen variant="section" />}</section>;
  return <section className="feed event-management"><button className="text-back" type="button" onClick={onBack}>← Назад</button><p className="section-kicker">Управление событием</p><h1>{event.title}</h1>{event.pending_status === "pending" && <p className="management-notice">Изменения проверяются. Пользователи пока видят прежнюю версию.</p>}{event.pending_status === "rejected" && <p className="form-error">Изменение отклонено: {event.rejection_reason}. Исправьте данные и отправьте снова.</p>}<label>Название<input value={title} maxLength={60} disabled={!event.can_edit} onChange={(e) => setTitle(e.target.value)} /></label><label>Описание<textarea value={description} maxLength={1000} disabled={!event.can_edit} onChange={(e) => setDescription(e.target.value)} /></label><div className="locked-event-field"><LockKeyhole /><span><small>Категория</small>{event.category}</span></div><div className="locked-event-field"><MapPin /><span><small>Место · {event.city}</small>{event.normalized_address}</span></div><div className="management-time"><CalendarClock /><div><label>Начало<input type="datetime-local" value={startsAt} disabled={!event.can_edit || !event.can_change_schedule} onChange={(e) => setStartsAt(e.target.value)} /></label><label>Окончание<input type="datetime-local" value={endsAt} disabled={!event.can_edit || !event.can_change_schedule} onChange={(e) => setEndsAt(e.target.value)} /></label></div></div>{!event.can_change_schedule && <p className="state-hint">Единственная смена даты и времени уже использована.</p>}<img className="management-photo" src={event.photo_url} alt="Текущая фотография события" />{event.can_edit && <EventPhotoUploader csrfToken={csrfToken} value={photo} onChange={setPhoto} />}{event.can_edit && <Button disabled={busy || !title.trim() || !description.trim()} onClick={() => void submit()}>{busy ? "Отправляем…" : "Отправить изменения на проверку"}</Button>}{message && <p className="success-message" role="status">{message}</p>}<EventRoster eventId={eventId} csrfToken={csrfToken} />{event.can_cancel && <div className="cancel-event"><h2>Отменить событие</h2><select value={cancelReason} onChange={(e) => setCancelReason(e.target.value)}>{cancelReasons.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><Button variant="outline" disabled={busy} onClick={() => void cancel()}>Отменить событие</Button></div>}</section>;
}

function EventRoster({ eventId, csrfToken }: { eventId: string; csrfToken: string }) {
  const [participants, setParticipants] = useState<RosterParticipant[] | null>(null);
  const [waitlist, setWaitlist] = useState<RosterWaiter[]>([]);
  const [selected, setSelected] = useState<RosterParticipant | null>(null);
  const [reason, setReason] = useState("rules_violation");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const load = async () => {
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/manage/roster`, { credentials: "include" });
    if (!response.ok) { setParticipants([]); return; }
    const data = await response.json() as { participants: RosterParticipant[]; waitlist: RosterWaiter[] };
    setParticipants(data.participants); setWaitlist(data.waitlist);
  };
  useEffect(() => { void load(); }, [eventId]);
  const exclude = async () => {
    if (!selected) return;
    if (!await confirmExclude(selected.display_name)) return;
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/participants/${selected.participation_id}/exclude`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken },
      body: JSON.stringify({ reason, note: note.trim() || null }),
    });
    if (response.ok) { setMessage("Участник удалён. Первому человеку в очереди автоматически выдано свободное место."); setSelected(null); setNote(""); await load(); }
    else setMessage("Не удалось удалить участника.");
  };
  return <section className="event-roster"><h2>Участники</h2>{participants === null ? <LoadingScreen variant="section" /> : participants.length ? participants.map((item) => <div className="roster-row" key={item.participation_id}><span><strong>{item.display_name}</strong><small>ID {item.public_id}</small></span><Button variant="outline" onClick={() => setSelected(item)}>Удалить</Button></div>) : <p className="state-hint">Участников пока нет.</p>}<h2>Очередь</h2>{waitlist.length ? waitlist.map((item) => <div className="roster-row" key={item.public_id}><span><strong>№{item.position} · {item.display_name}</strong><small>ID {item.public_id}</small></span></div>) : <p className="state-hint">Очередь пуста.</p>}{selected && <div className="exclude-participant"><h3>Удалить {selected.display_name}</h3><select value={reason} onChange={(event) => setReason(event.target.value)}><option value="rules_violation">Нарушение правил</option><option value="disruptive_behavior">Мешает проведению события</option><option value="participant_request">По просьбе участника</option><option value="other">Другое</option></select>{reason === "other" && <textarea maxLength={300} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Объясните причину" />}<div className="roster-actions"><Button variant="outline" onClick={() => setSelected(null)}>Отмена</Button><Button disabled={reason === "other" && !note.trim()} onClick={() => void exclude()}>Подтвердить удаление</Button></div></div>}{message && <p className="state-hint" role="status">{message}</p>}</section>;
}

async function confirmExclude(name: string): Promise<boolean> {
  const text = `Удалить участника ${name}? Он потеряет доступ к закрытому адресу и не сможет вступить снова.`;
  const webApp = window.Telegram?.WebApp;
  if (webApp?.showConfirm) return await new Promise<boolean>((resolve) => webApp.showConfirm?.(text, resolve));
  return window.confirm(text);
}

function toMoscowInput(value: string): string {
  const date = new Date(value);
  return new Date(date.getTime() + 3 * 60 * 60 * 1000).toISOString().slice(0, 16);
}
function fromMoscowInput(value: string): string { return `${value}:00+03:00`; }
async function confirmCancel(): Promise<boolean> {
  const webApp = window.Telegram?.WebApp;
  const text = "Отменить событие? Участники получат уведомление, вернуть событие будет нельзя.";
  if (webApp?.showConfirm) return await new Promise<boolean>((resolve) => webApp.showConfirm?.(text, resolve));
  return window.confirm(text);
}
