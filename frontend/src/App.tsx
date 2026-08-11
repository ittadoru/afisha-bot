import { CalendarDays, Map, ShieldCheck, Users } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";

import { MiniAppAuth } from "@/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingScreen } from "@/components/ui/loading-screen";
import { appConfig } from "@/config";

const MiniApp = lazy(async () => ({ default: (await import("@/components/mini-app")).MiniApp }));
const AdminApp = lazy(async () => ({ default: (await import("@/admin-app")).AdminApp }));

const benefits = [
  { icon: Map, title: "Смотрите, что происходит", text: "События и встречи рядом на одной понятной карте." },
  { icon: Users, title: "Участвуйте бесплатно", text: "Выбирайте компанию и занимайте место без платы за участие." },
  { icon: ShieldCheck, title: "Встречайтесь спокойнее", text: "Понятные правила, модерация и история организатора." },
];

export default function App() {
  if (window.location.hostname === "admin.podvval.xyz") return <Suspense fallback={<LoadingScreen />}><AdminApp /></Suspense>;
  return <BrowserRouter><Routes>
    <Route path="/" element={<LandingPage />} />
    <Route path="/event/:eventId" element={<PublicEventRoute />} />
    <Route path="/app/*" element={<MiniAppRoute />} />
    <Route path="*" element={<LandingPage />} />
  </Routes></BrowserRouter>;
}

function MiniAppRoute() {
  return <MiniAppAuth>{({ profile, csrfToken, updateProfile, logout }) => <Suspense fallback={<LoadingScreen />}><MiniApp profile={profile} csrfToken={csrfToken} onProfileUpdate={updateProfile} onLogout={logout} /></Suspense>}</MiniAppAuth>;
}

function LandingPage() {
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Afisha, на главную">Афиша</a>
        <Button variant="ghost" asChild><a href="/app">Открыть карту</a></Button>
      </header>

      <section id="top" className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <span className="eyebrow"><CalendarDays aria-hidden="true" /> Дагестан встречается здесь</span>
          <h1 id="hero-title">Есть куда пойти.<br />Есть с кем.</h1>
          <p>Карта бесплатных событий и встреч в крупных городах Дагестана.</p>
          <Button className="hero-action" asChild><a href="/app">Ехала →</a></Button>
        </div>
        <div className="dagestan-motif" aria-hidden="true">
          <span className="sun" />
          <span className="mountain mountain-back" />
          <span className="mountain mountain-front" />
          <span className="sea-line sea-one" />
          <span className="sea-line sea-two" />
        </div>
      </section>

      <section className="benefit-grid" aria-label="О сервисе">
        {benefits.map(({ icon: Icon, title, text }) => (
          <Card key={title}>
            <CardHeader>
              <span className="benefit-icon"><Icon aria-hidden="true" /></span>
              <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent><p>{text}</p></CardContent>
          </Card>
        ))}
      </section>
    </main>
  );
}

function PublicEventRoute() {
  const { eventId } = useParams();
  return eventId ? <PublicEventPage eventId={eventId} /> : <LandingPage />;
}

function PublicEventPage({ eventId }: { eventId: string }) {
  const [event, setEvent] = useState<{ id: string; kind: string; title: string; description: string; category: string; starts_at: string; ends_at: string; visible_address: string; photo_url: string; photo_card_url?: string; organizer_name: string | null; organizer_public_id: string | null; organizer_status: string | null; lifecycle_status: string } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { void fetch(`${appConfig.apiBaseUrl}/events/${eventId}`).then(async (response) => { if (!response.ok) throw new Error(); return await response.json(); }).then(setEvent).catch(() => setFailed(true)); }, [eventId]);
  if (failed) return <main className="public-event-page"><section className="public-event-card"><h1>Событие недоступно</h1><p>Возможно, оно ещё не опубликовано или было скрыто.</p><Button asChild><a href="/">На главную</a></Button></section></main>;
  if (!event) return <LoadingScreen />;
  return <main className="public-event-page"><header className="site-header"><a className="brand" href="/">Афиша</a><Button asChild><a href={`/app/event/${event.id}`}>Открыть Mini App</a></Button></header><article className={`public-event-card${event.kind === "special" ? " special-event" : ""}`}><img src={event.photo_url} srcSet={event.photo_card_url ? `${event.photo_card_url} 640w, ${event.photo_url} 1200w` : undefined} sizes="(max-width: 720px) calc(100vw - 32px), 640px" width="1200" height="900" decoding="async" fetchPriority="high" alt={`Фотография события «${event.title}»`} /><div><span className="category-chip">{event.kind === "special" ? "Особое · Общественное событие" : event.category}</span><h1>{event.title}</h1><p><CalendarDays /> {new Date(event.starts_at).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" })}</p><p><Map /> {event.visible_address}</p>{event.lifecycle_status === "cancelled" && <p className="form-error">Событие отменено</p>}<p className="public-event-description">{event.description}</p>{event.kind === "regular" && <p><strong>Организатор:</strong> {event.organizer_name} · {event.organizer_status === "trusted" ? "доверенный" : "новый"}</p>}<Button asChild><a href={`/app/event/${event.id}`}>Открыть в приложении</a></Button></div></article></main>;
}
