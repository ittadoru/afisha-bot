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
import { appConfig } from "@/config";
import { Button } from "@/components/ui/button";
import { LoadingScreen } from "@/components/ui/loading-screen";

interface EventMapProps {
  onBack?: () => void;
  onOpenPhoto?: () => void;
  embedded?: boolean;
  city?: MapCity;
  selecting?: boolean;
  onLocationChange?: (location: ResolvedLocation | null) => void;
  onOpenEvent?: (eventId: string) => void;
  onOpenStreetGroup?: (eventIds: string[], street: string) => void;
  onOpenList?: () => void;
}

export interface MapCity {
  id: string;
  name: string;
  center_latitude: number;
  center_longitude: number;
  service_radius_m?: number;
  map_bounds?: { west: number; south: number; east: number; north: number };
  allowed_area?: Record<string, unknown>;
}

export interface ResolvedLocation {
  latitude: number;
  longitude: number;
  display_name: string;
  street: string | null;
  house_number: string | null;
  precision: "house" | "street" | "locality";
}

const DEFAULT_CITY: MapCity = { id: "", name: "Махачкала", center_latitude: 42.9831, center_longitude: 47.5047 };

type PublicMarker = {
  marker_type: "event" | "street";
  id: string | null;
  kind: "regular" | "special";
  category_slug: string | null;
  category: string | null;
  title: string | null;
  latitude: number;
  longitude: number;
  street_name: string | null;
  event_count: number | null;
  event_ids: string[] | null;
};

export function EventMap({ onBack, onOpenPhoto, embedded = false, city = DEFAULT_CITY, selecting = false, onLocationChange, onOpenEvent, onOpenStreetGroup, onOpenList }: EventMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const publicMarkersRef = useRef<Marker[]>([]);
  const callbacksRef = useRef({ onLocationChange, onOpenEvent, onOpenStreetGroup });
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [empty, setEmpty] = useState(false);
  const [markersLoading, setMarkersLoading] = useState(!selecting);
  const [address, setAddress] = useState(selecting ? "Двигайте карту, чтобы выбрать точное место" : "События выбранного города");

  useEffect(() => {
    callbacksRef.current = { onLocationChange, onOpenEvent, onOpenStreetGroup };
  }, [onLocationChange, onOpenEvent, onOpenStreetGroup]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const bounds = city.map_bounds
      ? [[city.map_bounds.west, city.map_bounds.south], [city.map_bounds.east, city.map_bounds.north]] as [[number, number], [number, number]]
      : undefined;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: appConfig.mapStyleUrl,
      center: [city.center_longitude, city.center_latitude],
      zoom: 12,
      maxBounds: bounds,
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new AttributionControl({ compact: true }));
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");

    let requestId = 0;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    const eventsController = new AbortController();
    const resize = () => {
      map.resize();
      if (!bounds) return;
      const camera = map.cameraForBounds(bounds, { padding: 20 });
      if (camera?.zoom !== undefined) {
        map.setMinZoom(camera.zoom);
        if (map.getZoom() < camera.zoom) map.setZoom(camera.zoom);
      }
    };
    window.addEventListener("miniappviewportchange", resize);
    window.addEventListener("orientationchange", resize);
    const updateAddress = () => {
      if (!selecting || !city.id) return;
      window.clearTimeout(timer);
      controller?.abort();
      const currentRequest = ++requestId;
      timer = window.setTimeout(async () => {
        const { lng, lat } = map.getCenter();
        setAddress("Определяем адрес…");
        controller = new AbortController();
        try {
          const query = new URLSearchParams({ city_id: city.id, lat: String(lat), lon: String(lng) });
          const path = `/geo/resolve?${query.toString()}`;
          const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
            headers: { "Accept-Language": "ru" },
            signal: controller.signal,
          });
          if (response.status === 422) {
            if (currentRequest === requestId) {
              setAddress(`Выберите место не дальше ${Math.round((city.service_radius_m ?? 20_000) / 1000)} км от города ${city.name}`);
              callbacksRef.current.onLocationChange?.(null);
            }
            return;
          }
          if (!response.ok) throw new Error("location resolution failed");
          const data = (await response.json()) as { display_name: string; street: string | null; house_number: string | null; precision: "house" | "street" | "locality" };
          if (currentRequest === requestId) {
            setAddress(data.display_name);
            callbacksRef.current.onLocationChange?.({ latitude: lat, longitude: lng, display_name: data.display_name, street: data.street, house_number: data.house_number, precision: data.precision });
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") return;
          if (currentRequest === requestId) {
            setAddress("Адрес временно недоступен — место пока нельзя подтвердить");
            callbacksRef.current.onLocationChange?.(null);
          }
        }
      }, 500);
    };
    map.on("movestart", () => {
      if (!selecting) return;
      controller?.abort();
      setAddress("Выберите место и отпустите карту");
      callbacksRef.current.onLocationChange?.(null);
    });
    map.on("moveend", updateAddress);
    let ready = false;
    const initialLoadTimer = window.setTimeout(() => {
      if (!ready) setFailed(true);
    }, 15_000);
    map.once("idle", () => {
      ready = true;
      window.clearTimeout(initialLoadTimer);
    });
    map.on("load", () => {
      resize();
      if (city.allowed_area) {
        map.addSource("service-area", { type: "geojson", data: city.allowed_area as never });
        map.addLayer({ id: "service-area-fill", type: "fill", source: "service-area", paint: { "fill-color": "#08786c", "fill-opacity": 0.04 } });
        map.addLayer({ id: "service-area-line", type: "line", source: "service-area", paint: { "line-color": "#08786c", "line-width": 1.5, "line-opacity": 0.75 } });
      }
      if (selecting) {
        updateAddress();
        return;
      }
      if (!city.id) return;
      setMarkersLoading(true);
      publicMarkersRef.current.forEach((item) => item.remove());
      publicMarkersRef.current = [];
      void fetch(`${appConfig.apiBaseUrl}/events?city_id=${encodeURIComponent(city.id)}&view=map`, { credentials: "include", signal: eventsController.signal })
        .then(async (response) => {
          if (!response.ok) throw new Error();
          return await response.json() as { items: PublicMarker[] };
        })
        .then(({ items }) => {
          setEmpty(items.length === 0);
          setMarkersLoading(false);
          publicMarkersRef.current = items.map((item) => {
            const element = document.createElement("button");
            element.type = "button";
            element.className = item.marker_type === "street"
              ? "street-event-marker"
              : `public-event-marker category-${item.category_slug ?? "other"}${item.kind === "special" ? " special" : ""}`;
            const markerContent = document.createElement("span");
            markerContent.className = item.marker_type === "street" ? "street-marker-shape" : "event-pin-shape";
            const markerLabel = document.createElement("span");
            markerLabel.className = "marker-label";
            markerLabel.textContent = item.marker_type === "street" ? String(item.event_count ?? 0) : item.kind === "special" ? "ОС" : categorySymbol(item.category_slug);
            markerContent.append(markerLabel);
            element.append(markerContent);
            element.title = item.marker_type === "street" ? `${item.street_name} · ${item.event_count}` : item.title ?? item.category ?? "Событие";
            element.setAttribute("aria-label", item.marker_type === "street" ? `Общая улица ${item.street_name}, событий ${item.event_count}` : `${item.category}: ${item.title}`);
            element.addEventListener("click", () => item.marker_type === "street" ? callbacksRef.current.onOpenStreetGroup?.(item.event_ids ?? [], item.street_name ?? "Улица") : item.id && callbacksRef.current.onOpenEvent?.(item.id));
            return new MapLibreMarker({ element, anchor: "bottom" })
              .setLngLat([item.longitude, item.latitude]).addTo(map);
          });
        })
        .catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === "AbortError")) { setEmpty(false); setMarkersLoading(false); }
        });
    });
    map.on("error", () => {
      // MapLibre can report recoverable tile errors. The initial-load timer
      // decides whether the map is truly unavailable instead of hiding it at
      // the first transient error.
    });

    return () => {
      window.clearTimeout(timer);
      controller?.abort();
      eventsController.abort();
      window.removeEventListener("miniappviewportchange", resize);
      window.removeEventListener("orientationchange", resize);
      window.clearTimeout(initialLoadTimer);
      publicMarkersRef.current.forEach((item) => item.remove());
      publicMarkersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, [city.id, city.center_latitude, city.center_longitude, city.name, city.map_bounds, city.allowed_area, retryKey, selecting]);

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
          <h1>Карта временно недоступна</h1>
          <p>Попробуйте загрузить её ещё раз или откройте события списком.</p>
          <div className="map-fallback-actions">
            <Button onClick={() => { setFailed(false); setRetryKey((value) => value + 1); }}><RefreshCw aria-hidden="true" /> Повторить</Button>
            {onOpenList && <Button variant="outline" onClick={onOpenList}><List aria-hidden="true" /> Открыть список</Button>}
          </div>
        </section>
      ) : (
        <section className="map-shell" aria-label="Карта событий">
          <div ref={containerRef} className="map-canvas" />
          {selecting && <span className="fixed-location-marker" aria-label="Центр выбранного места" role="img">●</span>}
          {selecting && <p className="sr-only" aria-live="polite">{address}</p>}
          {markersLoading && <LoadingScreen variant="overlay" />}
          {empty && <div className="map-empty-chip">Пока тихо — создайте первое событие</div>}
        </section>
      )}
    </section>
  );
}

function categorySymbol(slug: string | null): string {
  return ({ sport: "СП", games: "ИГ", cinema: "КИ", music: "МУ", walks: "ПР", tourism: "ТУ", cars: "АВ", cafe: "КА", education: "ОБ", creativity: "ТВ", volunteering: "ВО", work: "РА" } as Record<string, string>)[slug ?? ""] ?? "СО";
}
