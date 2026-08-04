import { CalendarDays, Map, ShieldCheck, Users } from "lucide-react";
import { lazy, Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const EventMap = lazy(async () => ({ default: (await import("@/components/event-map")).EventMap }));
const PhotoCropper = lazy(async () => ({ default: (await import("@/components/photo-cropper")).PhotoCropper }));

type View = "landing" | "map" | "photo";

const benefits = [
  { icon: Map, title: "Смотрите, что происходит", text: "События и встречи рядом на одной понятной карте." },
  { icon: Users, title: "Участвуйте бесплатно", text: "Выбирайте компанию и занимайте место без платы за участие." },
  { icon: ShieldCheck, title: "Встречайтесь спокойнее", text: "Понятные правила, модерация и история организатора." },
];

export default function App() {
  const [view, setView] = useState<View>(() => window.location.pathname.startsWith("/app") ? "map" : "landing");

  if (view === "map") {
    return <Suspense fallback={<LoadingScreen />}><EventMap onBack={() => window.location.assign("/")} onOpenPhoto={() => setView("photo")} /></Suspense>;
  }

  if (view === "photo") {
    return <Suspense fallback={<LoadingScreen />}><PhotoCropper onBack={() => setView("map")} /></Suspense>;
  }

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

function LoadingScreen() {
  return <main className="loading-screen" role="status" aria-live="polite">Открываем…</main>;
}
