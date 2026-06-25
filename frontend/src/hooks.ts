import { useCallback, useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  error: { status: number; detail: string } | null;
  loading: boolean;
  refresh: () => void;
}

export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [state, setState] = useState<Omit<AsyncState<T>, "refresh">>({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let active = true;
    setState({ data: null, error: null, loading: true });
    loader()
      .then((data) => active && setState({ data, error: null, loading: false }))
      .catch((err) => active && setState({ data: null, error: err, loading: false }));
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, refresh };
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const diff = now - d.getTime();
  const h = diff / 3600000;
  if (h < 1) return `${Math.floor(diff / 60000)}m ago`;
  if (h < 24) return `${Math.floor(h)}h ago`;
  const days = Math.floor(h / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

export function formatMs(ms: number | null): string {
  if (ms == null) return "--";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}
