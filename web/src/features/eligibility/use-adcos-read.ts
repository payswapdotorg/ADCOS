"use client";

/**
 * useAdcosRead — Worker 2's shared in-memory read discipline.
 *
 * Every feature page reads backend truth through this ONE hook:
 *
 * - the fetcher runs through the session's typed client (Worker 1's
 *   transport — never a second one);
 * - `deps` re-run the read when the identity of the requested resource
 *   changes (contract id, filters, ...);
 * - `refresh()` re-runs the read on demand — refresh ALWAYS re-fetches
 *   truth from the backend (React state holds presentation only; there
 *   is deliberately NO cache: the backend is the single authority);
 * - passing `null` as the fetcher suspends the read (used to gate
 *   authenticated reads behind the session state);
 * - errors are stored raw (AdcosApiError carries the VERBATIM reason)
 *   and rendered through the shared ErrorState.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface AdcosReadState<T> {
  /** The last successfully fetched payload (null until first success). */
  data: T | null;
  /** True while a fetch is in flight (also true on the first suspended→run transition). */
  loading: boolean;
  /** The raw error of the last failed fetch (AdcosApiError or synthesized). */
  error: unknown;
  /** True once at least one fetch completed (success or failure). */
  loaded: boolean;
  /** Re-run the read now (manual refresh / post-mutation re-fetch). */
  refresh: () => void;
}

export function useAdcosRead<T>(
  fetcher: (() => Promise<T>) | null,
  deps: readonly unknown[],
): AdcosReadState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loaded, setLoaded] = useState(false);
  const [tick, setTick] = useState(0);
  const [loading, setLoading] = useState(fetcher !== null);

  // the fetcher identity changes every render by construction — keep the
  // latest one in a ref so the effect stays keyed on deps + tick only
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const activeRef = useRef(fetcher !== null);
  const wasActiveRef = useRef(fetcher !== null);

  useEffect(() => {
    const current = fetcherRef.current;
    const suspended = current === null;
    if (suspended) {
      // leaving the suspended state restarts the loading phase
      if (wasActiveRef.current) {
        setLoading(false);
      }
      wasActiveRef.current = false;
      activeRef.current = false;
      return;
    }
    wasActiveRef.current = true;
    activeRef.current = true;
    let cancelled = false;
    setLoading(true);
    current()
      .then((value) => {
        if (cancelled) return;
        setData(value);
        setError(null);
        setLoaded(true);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(caught);
        setLoaded(true);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const refresh = useCallback(() => {
    setTick((value) => value + 1);
  }, []);

  return { data, loading, error, loaded, refresh };
}
