import { ArrowLeft, Camera, List, MapPin, RefreshCw } from "lucide-react";
import {
  AttributionControl,
  Map as MapLibreMap,
  Marker as MapLibreMarker,
  NavigationControl,
  type Map as MapInstance,
  type Marker,
} from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import cafeIcon from "@mapbox/maki/icons/cafe.svg?raw";

import { getReverseGeocodeGeoReverseGetUrl } from "@/api/generated/afisha";
import { appConfig } from "@/config";
import { Button } from "@/components/ui/button";

interface EventMapProps {
  onBack?: () => void;
  onOpenPhoto?: () => void;
  embedded?: boolean;
}

const MAKHACHKALA: [number, number] = [47.5047, 42.9831];

export function EventMap({ onBack, onOpenPhoto, embedded = false }: EventMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const [failed, setFailed] = useState(false);
  const [address, setAddress] = useState("Переместите метку, чтобы уточнить адрес");

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: appConfig.mapStyleUrl,
      center: MAKHACHKALA,
      zoom: 12,
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new AttributionControl({ compact: true }));
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");

    const element = document.createElement("button");
    element.className = "event-marker";
    element.type = "button";
    element.setAttribute("aria-label", "Точное место выбранного события");
    element.innerHTML = cafeIcon;
    element.firstElementChild?.setAttribute("aria-hidden", "true");
    const marker = new MapLibreMarker({ element, draggable: true })
      .setLngLat(MAKHACHKALA)
      .addTo(map);
    markerRef.current = marker;

    let requestId = 0;
    let timer: number | undefined;
    const updateAddress = () => {
      window.clearTimeout(timer);
      const currentRequest = ++requestId;
      timer = window.setTimeout(async () => {
        const { lng, lat } = markerRef.current?.getLngLat() ?? { lng: 0, lat: 0 };
        setAddress("Определяем адрес…");
        try {
          const path = getReverseGeocodeGeoReverseGetUrl({ lat, lon: lng });
          const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
            headers: { "Accept-Language": "ru" },
          });
          if (!response.ok) throw new Error("reverse geocoding failed");
          const data = (await response.json()) as { display_name: string };
          if (currentRequest === requestId) setAddress(data.display_name);
        } catch {
          if (currentRequest === requestId) setAddress("Адрес временно недоступен — публикация будет заблокирована");
        }
      }, 500);
    };
    marker.on("dragend", updateAddress);
    map.on("error", () => setFailed(true));

    return () => {
      window.clearTimeout(timer);
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <section className={`workspace${embedded ? " embedded-map" : ""}`}>
      {!embedded && <header className="workspace-header">
        <Button variant="ghost" size="icon" onClick={onBack} aria-label="Вернуться на главную"><ArrowLeft /></Button>
        <div><strong>Махачкала</strong><span>События сегодня</span></div>
        <Button variant="outline" onClick={onOpenPhoto}><Camera aria-hidden="true" /> Фото</Button>
      </header>}

      {failed ? (
        <section className="map-fallback" role="alert">
          <List aria-hidden="true" />
          <h1>Карта сейчас недоступна</h1>
          <p>События остаются доступны списком. Скрытые координаты не раскрываются.</p>
          <Button onClick={() => window.location.reload()}><RefreshCw aria-hidden="true" /> Повторить</Button>
        </section>
      ) : (
        <section className="map-shell" aria-label="Карта событий">
          <div ref={containerRef} className="map-canvas" />
          <aside className="map-address" aria-live="polite">
            <MapPin aria-hidden="true" />
            <div><strong>Выбранное место</strong><span>{address}</span></div>
          </aside>
          <div className="map-legend"><span className="legend-exact" /> Точное место <span className="legend-street" /> Общая улица</div>
        </section>
      )}
    </section>
  );
}
