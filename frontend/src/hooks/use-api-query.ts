import { useCallback, useEffect, useRef, useState } from "react";

import { invalidateQueries, peekQuery, queryJson } from "@/lib/query-cache";

export function useApiQuery<T>(key: string, url: string | null, ttlMs: number) {
  const [data, setData] = useState<T | undefined>(() => peekQuery<T>(key));
  const [error, setError] = useState<Error | null>(null);
  const generation = useRef(0);

  const load = useCallback(async (force = false) => {
    if (!url) return;
    const current = ++generation.current;
    if (force) invalidateQueries(key);
    setError(null);
    try {
      const next = await queryJson<T>(key, url, ttlMs);
      if (generation.current === current) setData(next);
    } catch (reason) {
      if (generation.current === current) setError(reason instanceof Error ? reason : new Error("query_failed"));
    }
  }, [key, ttlMs, url]);

  useEffect(() => {
    setData(peekQuery<T>(key));
    void load();
    return () => { generation.current += 1; };
  }, [key, load]);

  return { data, error, loading: data === undefined && error === null, retry: () => load(true) };
}
