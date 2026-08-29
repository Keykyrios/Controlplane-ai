import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Hook for polling an API endpoint at a fixed interval.
 * Returns { data, loading, error, refresh }.
 */
export function usePolling(fetchFn, intervalMs = 5000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const result = await fetchFn();
      if (result) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    refresh();
    intervalRef.current = setInterval(refresh, intervalMs);
    return () => clearInterval(intervalRef.current);
  }, [refresh, intervalMs]);

  return { data, loading, error, refresh };
}

/**
 * Hook for tracking time since last update — shows "2s ago", "45s ago", etc.
 */
export function useTimeSince(timestamp) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!timestamp) return;
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - timestamp) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [timestamp]);

  if (elapsed < 5) return 'now';
  if (elapsed < 60) return `${elapsed}s ago`;
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m ago`;
  return `${Math.floor(elapsed / 3600)}h ago`;
}
