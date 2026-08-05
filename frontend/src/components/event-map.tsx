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

import { appConfig } from "@/config";
import { Button } from "@/components/ui/button";

interface EventMapProps {
  onBack?: () => void;
  onOpenPhoto?: () => void;
  embedded?: boolean;
  city?: MapCity;
  selecting?: boolean;
  onLocationChange?: (location: ResolvedLocation | null) => void;
}

export interface MapCity {
  id: string;
  name: string;
  center_latitude: number;
  center_longitude: number;
}

export interface ResolvedLocation {
  latitude: number;
  longitude: number;
  display_name: string;
  street: string | null;
}

const DEFAULT_CITY: MapCity = { id: "", name: "Махачкала", center_latitude: 42.9831, center_longitude: 47.5047 };

export function EventMap({ onBack, onOpenPhoto, embedded = false, city = DEFAULT_CITY, selecting = false, onLocationChange }: EventMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const [failed, setFailed] = useState(false);
  const [address, setAddress] = useState(selecting ? "Нажмите на карту или переместите метку" : "События выбранного города");

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: appConfig.mapStyleUrl,
      center: [city.center_longitude, city.center_latitude],
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
    const marker = new MapLibreMarker({ element, draggable: selecting })
      .setLngLat([city.center_longitude, city.center_latitude])
      .addTo(map);
    markerRef.current = marker;

    let requestId = 0;
    let timer: number | undefined;
    const updateAddress = () => {
      if (!selecting || !city.id) return;
      window.clearTimeout(timer);
      const currentRequest = ++requestId;
      timer = window.setTimeout(async () => {
        const { lng, lat } = markerRef.current?.getLngLat() ?? { lng: 0, lat: 0 };
        setAddress("Определяем адрес…");
        try {
          const query = new URLSearchParams({ city_id: city.id, lat: String(lat), lon: String(lng) });
          const path = `/geo/resolve?${query.toString()}`;
          const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
            headers: { "Accept-Language": "ru" },
          });
          if (response.status === 422) {
            if (currentRequest === requestId) {
              setAddress(`Эта точка находится за границей города ${city.name}`);
              onLocationChange?.(null);
            }
            return;
          }
          if (!response.ok) throw new Error("location resolution failed");
          const data = (await response.json()) as { display_name: string; street: string | null };
          if (currentRequest === requestId) {
            setAddress(data.display_name);
            onLocationChange?.({ latitude: lat, longitude: lng, display_name: data.display_name, street: data.street });
          }
        } catch {
          if (currentRequest === requestId) {
            setAddress("Адрес временно недоступен — место пока нельзя подтвердить");
            onLocationChange?.(null);
          }
        }
      }, 500);
    };
    marker.on("dragend", updateAddress);
    map.on("click", (event) => {
      if (!selecting) return;
      marker.setLngLat(event.lngLat);
      updateAddress();
    });
    map.on("error", () => setFailed(true));

    return () => {
      window.clearTimeout(timer);
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [city.id, city.center_latitude, city.center_longitude, city.name, onLocationChange, selecting]);

  return (
    <section className={`workspace${embedded ? " embedded-map" : ""}`}>
      {!embedded && <header className="workspace-header">
        <Button variant="ghost" size="icon" onClick={onBack} aria-label="Вернуться на главную"><ArrowLeft /></Button>
        <div><strong>{city.name}</strong><span>События сегодня</span></div>
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
            <div><strong>{selecting ? "Выбранное место" : city.name}</strong><span>{address}</span></div>
          </aside>
          <div className="map-legend"><span className="legend-exact" /> Точное место <span className="legend-street" /> Общая улица</div>
        </section>
      )}
    </section>
  );
}
