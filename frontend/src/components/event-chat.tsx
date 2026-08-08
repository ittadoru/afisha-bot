import { MessageCircle, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { appConfig } from "@/config";
import { Button } from "@/components/ui/button";

interface ChatMessage {
  id: string;
  body: string;
  created_at: string;
  author_display_name: string;
  author_is_organizer: boolean;
}

interface EventChatProps {
  eventId: string;
  csrfToken: string;
  onClose: () => void;
}

function messageTime(value: string): string {
  return new Date(value).toLocaleString("ru-RU", { timeZone: "Europe/Moscow", hour: "2-digit", minute: "2-digit" });
}

export function EventChat({ eventId, csrfToken, onClose }: EventChatProps) {
  const [chatEnabled, setChatEnabled] = useState(true);
  const [viewerIsOrganizer, setViewerIsOrganizer] = useState(false);
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(0);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<string | null>(null);
  useEffect(() => {
    messagesRef.current = messages.length > 0 ? messages[messages.length - 1].id : null;
  }, [messages]);

  useEffect(() => {
    let active = true;
    void fetch(`${appConfig.apiBaseUrl}/events/${eventId}`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        return await response.json() as { title: string; chat_enabled: boolean; viewer_is_organizer: boolean };
      })
      .then((event) => {
        if (!active) return;
        setTitle(event.title);
        setChatEnabled(event.chat_enabled);
        setViewerIsOrganizer(event.viewer_is_organizer);
      })
      .catch(() => { if (active) setError("Не получилось загрузить чат."); });
    return () => { active = false; };
  }, [eventId]);

  const load = useCallback(async () => {
    const last = messagesRef.current;
    const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/chat${last ? `?after=${last}` : ""}`, { credentials: "include" });
    if (!response.ok) return;
    const data = await response.json() as { items: ChatMessage[] };
    setMessages((current) => {
      const known = new Set(current.map((item) => item.id));
      const fresh = data.items.filter((item) => !known.has(item.id));
      return fresh.length ? [...current, ...fresh] : current;
    });
  }, [eventId]);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => { void load(); }, 5000);
    return () => window.clearInterval(interval);
  }, [load]);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setInterval(() => setWait((value) => value - 1), 1000);
    return () => window.clearInterval(timer);
  }, [wait > 0]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 140;
    if (nearBottom) container.scrollTop = container.scrollHeight;
  }, [messages.length]);

  const send = async () => {
    const body = text.trim();
    if (!body || busy || wait > 0) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/chat`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ body }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null) as { detail?: string } | null;
        if (data?.detail === "rate_limited") setError("Слишком часто. Подождите несколько секунд.");
        else if (data?.detail === "chat_closed") setError("Чат закрыт организатором.");
        else setError("Не удалось отправить сообщение.");
        return;
      }
      const item = await response.json() as { message: ChatMessage };
      setMessages((current) => [...current, item.message]);
      setText("");
      setWait(3);
    } catch {
      setError("Не удалось отправить сообщение.");
    } finally {
      setBusy(false);
    }
  };

  const toggle = async () => {
    if (toggling) return;
    setToggling(true); setError("");
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/chat`, {
        method: "PUT", credentials: "include",
        headers: { "Content-Type": "application/json", "X-Afisha-CSRF": csrfToken, "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ enabled: !chatEnabled }),
      });
      if (!response.ok) throw new Error();
      setChatEnabled((await response.json() as { chat_enabled: boolean }).chat_enabled);
    } catch {
      setError("Не удалось изменить состояние чата.");
    } finally {
      setToggling(false);
    }
  };

  return <section className="feed page-screen chat-page">
    <button className="text-back" type="button" onClick={onClose}>← Назад</button>
    <header className="chat-header"><MessageCircle aria-hidden="true" /><h1>{title || "Чат события"}{chatEnabled ? "" : " (закрыт)"}</h1>{viewerIsOrganizer && <button type="button" className="chat-toggle" disabled={toggling} onClick={() => void toggle()}>{chatEnabled ? "Закрыть чат" : "Открыть чат"}</button>}</header>
    <div className="chat-messages" ref={scrollRef} aria-live="polite">
      {messages.map((item) => (
        <article className={`chat-message${item.author_is_organizer ? " organizer" : ""}`} key={item.id}>
          <small>{item.author_is_organizer ? `${item.author_display_name} · организатор` : item.author_display_name}</small>
          <p>{item.body}</p>
          <time>{messageTime(item.created_at)}</time>
        </article>
      ))}
      {messages.length === 0 && !error && <p className="state-hint">Сообщений пока нет. Будьте первым!</p>}
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {chatEnabled ? (
      <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); void send(); }}>
        <label className="visually-hidden" htmlFor="chat-body">Сообщение</label>
        <textarea id="chat-body" value={text} onChange={(event) => setText(event.target.value)} maxLength={500} placeholder="Напишите сообщение…" disabled={busy} />
        <Button disabled={busy || wait > 0 || !text.trim()} onClick={() => void send()}>{busy ? "Отправляем…" : wait > 0 ? `${wait} с` : <><Send aria-hidden="true" /> Отправить</>}</Button>
      </form>
    ) : <p className="state-hint">Чат закрыт организатором.</p>}
  </section>;
}