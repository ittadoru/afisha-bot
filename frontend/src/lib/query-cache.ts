type Entry<T> = {
  data?: T;
  expiresAt: number;
  lastUsedAt: number;
  promise?: Promise<T>;
};

const entries = new Map<string, Entry<unknown>>();
const MAX_IDLE_MS = 30 * 60_000;

export async function queryJson<T>(key: string, url: string, ttlMs: number): Promise<T> {
  const now = Date.now();
  const existing = entries.get(key) as Entry<T> | undefined;
  if (existing?.data !== undefined && existing.expiresAt > now) {
    existing.lastUsedAt = now;
    return existing.data;
  }
  if (existing?.promise) return existing.promise;

  const entry: Entry<T> = existing ?? { expiresAt: 0, lastUsedAt: now };
  const request = fetch(url, { credentials: "include" }).then(async (response) => {
    if (!response.ok) throw new Error(`query_failed_${response.status}`);
    const data = await response.json() as T;
    entry.data = data;
    entry.expiresAt = Date.now() + ttlMs;
    entry.lastUsedAt = Date.now();
    return data;
  }).finally(() => { entry.promise = undefined; });
  entry.promise = request;
  entries.set(key, entry);
  pruneQueryCache(now);
  return request;
}

export function peekQuery<T>(key: string): T | undefined {
  return (entries.get(key) as Entry<T> | undefined)?.data;
}

export function invalidateQueries(prefix: string): void {
  for (const key of entries.keys()) if (key.startsWith(prefix)) entries.delete(key);
}

export function clearQueryCache(): void {
  entries.clear();
}

export function pruneQueryCache(now = Date.now()): void {
  for (const [key, entry] of entries) {
    if (!entry.promise && now - entry.lastUsedAt > MAX_IDLE_MS) entries.delete(key);
  }
}
