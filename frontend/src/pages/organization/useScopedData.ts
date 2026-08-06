/**
 * Load organization-scoped data, and never render another organization's.
 *
 * The window this closes
 * ----------------------
 * Switching organization does not cancel a request that is already in flight.
 * That request carries the previous `X-Organization-Id`, so the backend
 * correctly answers it with the previous organization's rows — and the answer
 * arrives after the interface has visually moved on. Rendering it would put one
 * organization's members under another organization's name, which reads as a UI
 * glitch and is a disclosure.
 *
 * So every load records the generation it was issued in, and a response from a
 * superseded generation is discarded rather than rendered. The AbortController
 * cancels what it can; the generation check is what makes correctness not
 * depend on cancellation having won the race.
 *
 * State is cleared *synchronously* when the generation changes, before the new
 * request goes out. Clearing on arrival would leave the previous
 * organization's data on screen for the duration of the fetch.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import type { ApiResult } from '../../api/types';
import {
  currentGeneration, getActiveOrganizationId, isCurrentGeneration,
  subscribeToActiveOrganization,
} from '../../organizations/activeOrganization';
import { useOrganization } from '../../organizations/OrganizationContext';

export interface ScopedData<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useScopedData<T>(
  load: (signal: AbortSignal) => Promise<ApiResult<T>>,
  deps: ReadonlyArray<unknown>,
): ScopedData<T> {
  const { generation } = useOrganization();
  // Read from the module rather than from React state, and subscribe to it.
  //
  // The module value is what `apiRequest` puts in the header, so it is the
  // organization the backend will actually answer for. Keying the load on the
  // context's copy instead would leave two sources of truth that can disagree
  // for a render — and the render they disagree in is the one showing another
  // organization's rows.
  const [activeId, setActiveId] = useState<number | null>(
    getActiveOrganizationId());
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);

  // Set on mount as well as cleared on unmount. Under StrictMode the effect
  // runs twice, and a cleanup-only version would leave the flag false for the
  // life of a component that is very much still mounted.
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => subscribeToActiveOrganization((id) => {
    if (mounted.current) setActiveId(id);
  }), []);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    // Synchronous clear. Anything already on screen belongs to the previous
    // organization until proven otherwise.
    setData(null);
    setError(null);
    setLoading(true);

    if (activeId === null) {
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    const issuedAt = currentGeneration();

    void (async () => {
      const result = await load(controller.signal);
      if (!mounted.current || controller.signal.aborted) return;
      // The authority on staleness. A response that arrives after a switch is
      // about an organization the user is no longer looking at.
      if (!isCurrentGeneration(issuedAt)) return;

      setLoading(false);
      if (result.status === 'error') {
        setError(result.error.message);
        return;
      }
      setData(result.data);
    })();

    return () => controller.abort();
    // `load` is intentionally not a dependency: callers pass an inline closure,
    // which would be a new reference every render and loop. The explicit deps
    // list is what the caller controls.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generation, activeId, nonce, ...deps]);

  return { data, loading, error, reload };
}
