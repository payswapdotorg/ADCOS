"use client";

/**
 * useDevelopersRead — the developers-area read hook.
 *
 * The same discipline Worker 2 established for the connectivity
 * surfaces (their `useAdcosRead` lives in Worker 2's feature tree,
 * which is not imported here): a null fetcher SUSPENDS the read (an
 * authenticated route is never fired while disconnected), `refresh`
 * re-fetches truth, and React state holds presentation only — the
 * backend remains the single authority.
 *
 * The fetcher is captured in a ref that always carries the LATEST
 * closure, while the effect re-runs only when the caller's deps or
 * the refresh tick change — so inline arrow fetchers don't loop.
 */

import { useEffect, useRef, useState } from "react";

/** The state of one suspended-or-active read. */
export interface DevelopersReadState<T> {
  /** The last resolved value (null until a fetch resolves). */
  data: T | null;
  /** A fetch for the CURRENT state is in flight. */
  loading: boolean;
  /** At least one fetch has resolved (data or error). */
  loaded: boolean;
  /** The last failure (typed AdcosApiError from the client). */
  error: unknown;
  /** Re-fetch (bumps the internal tick). */
  refresh: () => void;
}

/**
 * Read through the typed client. `fetcher` returning a promise of the
 * value to hold; pass `null` to suspend the read (e.g. while
 * disconnected). `deps` are the caller's identity inputs (client,
 * ids) — the effect re-runs when they change.
 */
export function useDevelopersRead<T>(
  fetcher: (() => Promise<T>) | null,
  deps: unknown[],
): DevelopersReadState<T> {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [tick, setTick] = useState(0);
  const [state, setState] = useState<{
    data: T | null;
    loading: boolean;
    loaded: boolean;
    error: unknown;
  }>(() => ({
    data: null,
    loading: fetcher !== null,
    loaded: false,
    error: null,
  }));

  useEffect(() => {
    const current = fetcherRef.current;
    if (current === null) {
      // suspended: nothing in flight, nothing to show
      setState((previous) =>
        previous.loading ? { ...previous, loading: false } : previous,
      );
      return;
    }
    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    current()
      .then((data) => {
        if (cancelled) return;
        setState({ data, loading: false, loaded: true, error: null });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState((previous) => ({
          data: previous.data,
          loading: false,
          loaded: true,
          error,
        }));
      });
    return () => {
      cancelled = true;
    };
    // the caller's deps + the refresh tick drive re-fetches; the
    // fetcher itself travels via ref (always the latest closure)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return {
    data: state.data,
    loading: state.loading,
    loaded: state.loaded,
    error: state.error,
    refresh: () => setTick((value) => value + 1),
  };
}
