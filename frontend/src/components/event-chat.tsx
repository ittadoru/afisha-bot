import { ArrowLeft, MessageCircle, MoreHorizontal, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { appConfig } from "@/config";
import { LoadingScreen } from "@/components/ui/loading-screen";

interface ChatMessage {
  id: string;
  body: string;
  created_at: string;
  author_display_name: string;
  author_public_id: string;
  author_avatar_thumbnail_url: string | null;
  author_is_organizer: boolean;
  author_is_viewer: boolean;
}

interface EventChatProps {
  eventId: string;
  csrfToken: string;
  onClose: () => void;
}

function ChatAvatar({ name, src }: { name: string; src: string | null }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed) return <span>{name[0] ?? "?"}</span>;
  return <img src={src} width="36" height="36" loading="lazy" decoding="async" alt="" onError={() => setFailed(true)} />;
}

function messageTime(value: string): string {
  return new Date(value).toLocaleString("ru-RU", { timeZone: "Europe/Moscow", hour: "2-digit", minute: "2-digit" });
}

export function EventChat({ eventId, csrfToken, onClose }: EventChatProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [chatEnabled, setChatEnabled] = useState(true);
  const [viewerIsOrganizer, setViewerIsOrganizer] = useState(false);
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(0);
  const [toggling, setToggling] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [error, setError] = useState("");
  const [eventLoaded, setEventLoaded] = useState(false);
  const [messagesLoaded, setMessagesLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const messagesRef = useRef<string | null>(null);
  useEffect(() => {
    messagesRef.current = messages.length > 0 ? messages[messages.length - 1].id : null;
  }, [messages]);

  useEffect(() => {
    let active = true;
    setEventLoaded(false);
    setMessagesLoaded(false);
    setMessages([]);
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
      .catch(() => { if (active) setError("Не получилось загрузить чат."); })
      .finally(() => { if (active) setEventLoaded(true); });
    return () => { active = false; };
  }, [eventId]);

  const load = useCallback(async () => {
    const last = messagesRef.current;
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/events/${eventId}/chat${last ? `?after=${last}` : ""}`, { credentials: "include" });
      if (!response.ok) return;
      const data = await response.json() as { items: ChatMessage[] };
      setMessages((current) => {
        const known = new Set(current.map((item) => item.id));
        const fresh = data.items.filter((item) => !known.has(item.id));
        return fresh.length ? [...current, ...fresh] : current;
      });
    } finally {
      setMessagesLoaded(true);
    }
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

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "0px";
    input.style.height = `${Math.min(input.scrollHeight, 112)}px`;
  }, [text]);

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

  if (!eventLoaded || !messagesLoaded) return <section className="chat-page"><LoadingScreen variant="section" /></section>;

  return <section className="chat-page">
    <header className="chat-appbar"><button type="button" aria-label="Вернуться к событию" onClick={onClose}><ArrowLeft aria-hidden="true" /></button><span><small>Чат события</small><strong>{title || "Чат события"}</strong></span><div className="chat-menu-wrap">{viewerIsOrganizer ? <><button type="button" aria-label="Настройки чата" aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}><MoreHorizontal aria-hidden="true" /></button>{menuOpen && <div className="chat-overflow-menu"><button type="button" disabled={toggling} onClick={() => { setMenuOpen(false); void toggle(); }}>{chatEnabled ? "Закрыть чат" : "Открыть чат"}</button></div>}</> : <MessageCircle aria-hidden="true" />}</div></header>
    <div className="chat-messages" ref={scrollRef} aria-live="polite">
      {messages.map((item, index) => {
        const previous = messages[index - 1];
        const showDay = !previous || messageDay(previous.created_at) !== messageDay(item.created_at);
        const compact = Boolean(previous && !showDay && previous.author_public_id === item.author_public_id && previous.author_is_organizer === item.author_is_organizer);
        const profilePath = item.author_is_viewer ? "/app/profile" : `/app/profile/${item.author_public_id}`;
        return <div className="chat-message-wrap" key={item.id}>{showDay && <time className="chat-day">{messageDayLabel(item.created_at)}</time>}<div className={`chat-message-row${item.author_is_viewer ? " viewer" : ""}${compact ? " compact" : ""}`}>
          {!compact ? <button className="chat-avatar-button" type="button" aria-label={`Открыть профиль ${item.author_display_name}`} onClick={() => navigate(profilePath, { state: { returnTo: location.pathname } })}><ChatAvatar name={item.author_display_name} src={item.author_avatar_thumbnail_url} /></button> : <span className="chat-avatar-spacer" aria-hidden="true" />}
          <article className={`chat-message${item.author_is_viewer ? " viewer" : ""}${item.author_is_organizer ? " organizer" : ""}${compact ? " compact" : ""}`}><div className="chat-author"><small>{item.author_is_viewer ? "Вы" : item.author_display_name}{item.author_is_organizer && <span>Организатор</span>}</small></div><p>{item.body}</p><time>{messageTime(item.created_at)}</time></article>
        </div></div>;
      })}
      {messages.length === 0 && !error && <div className="chat-empty"><MessageCircle aria-hidden="true" /><strong>Начните разговор</strong><p>Уточните детали встречи или просто поздоровайтесь.</p></div>}
    </div>
    {error && <p className="chat-error" role="alert">{error}</p>}
    {chatEnabled ? <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); void send(); }}><label className="sr-only" htmlFor="chat-body">Сообщение</label><div><textarea ref={inputRef} rows={1} id="chat-body" value={text} onChange={(event) => setText(event.target.value)} maxLength={500} placeholder="Сообщение…" disabled={busy} />{wait > 0 && <small>Можно отправить через {wait} с</small>}</div><button type="submit" aria-label="Отправить сообщение" disabled={busy || wait > 0 || !text.trim()}><Send aria-hidden="true" /></button></form> : <p className="chat-closed"><MessageCircle aria-hidden="true" />Чат закрыт организатором</p>}
  </section>;
}

function messageDay(value: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Moscow", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

function messageDayLabel(value: string): string {
  const key = messageDay(value);
  const today = messageDay(new Date().toISOString());
  const yesterday = messageDay(new Date(Date.now() - 86_400_000).toISOString());
  if (key === today) return "Сегодня";
  if (key === yesterday) return "Вчера";
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", day: "numeric", month: "long" }).format(new Date(value));
}
