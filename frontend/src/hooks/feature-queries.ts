import { appConfig } from "@/config";
import { useApiQuery } from "@/hooks/use-api-query";

const SECOND = 1_000;

export const queryKeys = {
  catalog: () => "catalog",
  events: (city: string, view: string) => `events:${city}:${view}`,
  event: (id: string) => `event:${id}`,
  profile: (id: string) => `profile:${id}`,
  company: (city: string, sort: string) => `company:${city}:${sort}`,
  notifications: (filter: string) => `notifications:${filter}`,
  cases: (status: string) => `cases:${status}`,
};

export function useCatalog<T>() {
  return useApiQuery<T>(queryKeys.catalog(), `${appConfig.apiBaseUrl}/geo/catalog`, 30 * 60 * SECOND);
}

export function useEvents<T>(city: string | null, view: "map" | "list") {
  return useApiQuery<T>(queryKeys.events(city ?? "none", view), city ? `${appConfig.apiBaseUrl}/events?city_id=${encodeURIComponent(city)}&view=${view}` : null, 30 * SECOND);
}

export function useEvent<T>(id: string | null) {
  return useApiQuery<T>(queryKeys.event(id ?? "none"), id ? `${appConfig.apiBaseUrl}/events/${id}` : null, 60 * SECOND);
}

export function useProfile<T>(publicId: string | null) {
  return useApiQuery<T>(queryKeys.profile(publicId ?? "none"), publicId ? `${appConfig.apiBaseUrl}/profiles/${publicId}` : null, 60 * SECOND);
}

export function useLookingPosts<T>(city: string | null, sort: string) {
  return useApiQuery<T>(queryKeys.company(city ?? "none", sort), city ? `${appConfig.apiBaseUrl}/looking-posts?city_id=${encodeURIComponent(city)}&sort=${encodeURIComponent(sort)}` : null, 30 * SECOND);
}

export function useNotifications<T>(filter: "all" | "unread") {
  return useApiQuery<T>(queryKeys.notifications(filter), `${appConfig.apiBaseUrl}/account/notifications/feed?filter=${filter}`, 15 * SECOND);
}

export function useCases<T>(status: "active" | "resolved") {
  return useApiQuery<T>(queryKeys.cases(status), `${appConfig.apiBaseUrl}/account/cases?status=${status}&limit=20`, 15 * SECOND);
}
