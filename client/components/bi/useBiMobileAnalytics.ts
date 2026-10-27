import { useCallback, useEffect, useRef, useState } from "react";
import {
  biApi,
  type ApiBIMobileAnalytics,
  type ApiBIMobileFilters,
} from "@/lib/api";

export const BI_REFRESH_MS = Math.max(
  10000,
  Number(import.meta.env.VITE_BI_REFRESH_MS) || 30000,
);

export function useBiMobileAnalytics(filters: ApiBIMobileFilters) {
  const key = JSON.stringify(filters);
  const cache = useRef(new Map<string, ApiBIMobileAnalytics>());
  const cachedAt = useRef(new Map<string, number>());
  const pending = useRef(new Map<string, Promise<ApiBIMobileAnalytics>>());
  const currentKey = useRef(key);
  currentKey.current = key;
  const [state, setState] = useState<{
    key: string;
    data: ApiBIMobileAnalytics | null;
    loading: boolean;
    refreshing: boolean;
    error: string | null;
  }>({ key, data: null, loading: true, refreshing: false, error: null });

  const load = useCallback(async () => {
    const cached = cache.current.get(key);
    setState({
      key,
      data: cached ?? null,
      loading: !cached,
      refreshing: !!cached,
      error: null,
    });
    let request = pending.current.get(key);
    if (!request) {
      request = biApi.mobileAnalytics(JSON.parse(key));
      pending.current.set(key, request);
    }
    try {
      const data = await request;
      cache.current.set(key, data);
      cachedAt.current.set(key, Date.now());
      if (cache.current.size > 32) {
        const oldest = cache.current.keys().next().value;
        cache.current.delete(oldest);
        cachedAt.current.delete(oldest);
      }
      if (currentKey.current === key)
        setState({
          key,
          data,
          loading: false,
          refreshing: false,
          error: null,
        });
    } catch (error) {
      if (currentKey.current === key)
        setState({
          key,
          data: cached ?? null,
          loading: false,
          refreshing: false,
          error:
            error instanceof Error
              ? error.message
              : "Falha de conexão ao carregar o BI.",
        });
    } finally {
      if (pending.current.get(key) === request) pending.current.delete(key);
    }
  }, [key]);

  useEffect(() => {
    const cached = cache.current.get(key);
    if (cached)
      setState({
        key,
        data: cached,
        loading: false,
        refreshing: false,
        error: null,
      });
    if (
      !cached ||
      Date.now() - (cachedAt.current.get(key) ?? 0) >= BI_REFRESH_MS
    )
      void load();
    const refreshVisible = () => {
      if (document.visibilityState !== "hidden") void load();
    };
    const interval = window.setInterval(refreshVisible, BI_REFRESH_MS);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [key, load]);

  return {
    ...(state.key === key
      ? state
      : { data: null, loading: true, refreshing: false, error: null }),
    refresh: load,
  };
}
