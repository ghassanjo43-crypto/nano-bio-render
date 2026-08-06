/**
 * Organization selection, and everything that must be discarded when it changes.
 *
 * The rule this file exists to enforce
 * ------------------------------------
 * **Nothing cached under one organization may ever be rendered under another.**
 *
 * That is stricter than "reload after switching". Reloading still leaves a
 * window — usually a few hundred milliseconds — in which the previous
 * organization's studies are on screen beneath the new organization's name.
 * Anyone watching would reasonably read that as the new organization's data.
 *
 * So the order is: clear first, then fetch. `clearOrganizationScopedState`
 * runs synchronously during the switch, before any new request is issued, and
 * consumers render an explicit loading state rather than stale content.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef,
  useState, type ReactNode,
} from 'react';

import { apiRequest } from '../api/client';
import {
  currentGeneration, getActiveOrganizationId, isCurrentGeneration,
  setActiveOrganizationId,
} from './activeOrganization';

export interface OrganizationSummary {
  id: number;
  slug: string;
  name: string;
  status: string;
  is_legacy: boolean;
  awaiting_confirmation: boolean;
  your_role: string;
  your_scope: string;
  is_administrative: boolean;
  may_download_attachments: boolean;
}

/** Why the workspace is unusable, when it is. */
export type OrganizationProblem =
  | 'none'
  /** Authenticated, but a member of nothing. An administrator must act. */
  | 'no_memberships'
  /** Several organizations and no choice made. The contract forbids guessing. */
  | 'selection_required'
  /** The stored selection is gone: revoked, expired, suspended or archived. */
  | 'selection_unavailable'
  /** The backend could not be reached. Distinct from "you have no access". */
  | 'unavailable';

interface OrganizationState {
  organizations: OrganizationSummary[];
  active: OrganizationSummary | null;
  activeId: number | null;
  problem: OrganizationProblem;
  loading: boolean;
  /** Increments on every switch. Consumers key caches on it. */
  generation: number;
  select: (id: number | null) => void;
  refresh: () => Promise<void>;
}

const OrganizationContext = createContext<OrganizationState | null>(null);

interface ListingBody {
  organizations: OrganizationSummary[];
  active_organization_id: number | null;
  requires_explicit_selection: boolean;
}

function isListing(body: unknown): body is ListingBody {
  return typeof body === 'object' && body !== null
    && Array.isArray((body as ListingBody).organizations);
}

/**
 * Everything keyed by organization that must not survive a switch.
 *
 * Deliberately a single exported function rather than scattered cleanup in
 * each consumer: a consumer added later would otherwise be the one that
 * forgets, and its stale data would be the one that shows.
 */
export function clearOrganizationScopedState(): void {
  const prefixes = [
    'nanobio.workflow.',     // pathway, active study, candidate
    'nanobio.registry.',     // registry filters and last-viewed experiment
    'nanobio.readiness.',    // readiness snapshots and area selections
    'nanobio.workspace.',    // project and run selections
  ];
  try {
    const store = globalThis.sessionStorage;
    if (!store) return;
    const doomed: string[] = [];
    for (let i = 0; i < store.length; i += 1) {
      const key = store.key(i);
      if (key && prefixes.some((p) => key.startsWith(p))) doomed.push(key);
    }
    for (const key of doomed) store.removeItem(key);
  } catch {
    /* storage unavailable: nothing cached, nothing to clear */
  }
}

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const [organizations, setOrganizations] = useState<OrganizationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(
    getActiveOrganizationId());
  const [problem, setProblem] = useState<OrganizationProblem>('none');
  const [loading, setLoading] = useState(true);
  const [generation, setGeneration] = useState(currentGeneration());
  const mounted = useRef(true);

  // Set on mount as well as cleared on unmount.
  //
  // A cleanup-only version is wrong under React StrictMode, which mounts,
  // unmounts and remounts every component in development: the cleanup fires,
  // the flag stays false for the life of a component that is very much still
  // mounted, and every response is then discarded as belonging to an unmounted
  // provider. The visible symptom is the switcher stuck on "Loading workspace…"
  // forever while the network tab shows a perfectly good 200 — which is how
  // this was found, by the browser walkthrough rather than by any unit test.
  //
  // The unit tests could not catch it because Testing Library renders without
  // StrictMode, so the double-invocation never happens there.
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const refresh = useCallback(async () => {
    const issuedAt = currentGeneration();
    setLoading(true);

    const result = await apiRequest<ListingBody>(
      '/api/v1/organizations', { method: 'GET' }, isListing);

    // A response from a superseded generation is discarded, not rendered.
    if (!mounted.current || !isCurrentGeneration(issuedAt)) return;

    if (result.status === 'error') {
      setLoading(false);
      // A 401 is handled globally by the session-expiry hook; anything else
      // here means the service is unreachable, which must not be reported to
      // the user as "you have no access".
      setProblem('unavailable');
      return;
    }

    const list = result.data.organizations;
    setOrganizations(list);
    setLoading(false);

    if (list.length === 0) {
      setProblem('no_memberships');
      setActiveOrganizationId(null);
      setActiveId(null);
      return;
    }

    const stored = getActiveOrganizationId();
    const storedStillValid = stored !== null
      && list.some((o) => o.id === stored);

    if (stored !== null && !storedStillValid) {
      // Revoked, expired, suspended, or the organization was archived.
      setActiveOrganizationId(null);
      setActiveId(null);
      clearOrganizationScopedState();
      setProblem('selection_unavailable');
      return;
    }

    if (storedStillValid) {
      setActiveId(stored);
      setProblem('none');
      return;
    }

    const only = list.length === 1 ? list[0] : undefined;
    if (only) {
      // The contract permits automatic selection only when there is exactly
      // one candidate, because then no choice is being made on the user's
      // behalf.
      setActiveOrganizationId(only.id);
      setActiveId(only.id);
      setProblem('none');
      return;
    }

    // Several organizations and nothing chosen. Never guess.
    setProblem('selection_required');
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const select = useCallback((id: number | null) => {
    if (id === getActiveOrganizationId()) return;
    // Clear before switching, so no render can occur with the previous
    // organization's data under the new organization's name.
    clearOrganizationScopedState();
    setActiveOrganizationId(id);
    setActiveId(id);
    setGeneration(currentGeneration());
    setProblem(id === null ? 'selection_required' : 'none');
    void refresh();
  }, [refresh]);

  const value = useMemo<OrganizationState>(() => ({
    organizations,
    active: organizations.find((o) => o.id === activeId) ?? null,
    activeId,
    problem,
    loading,
    generation,
    select,
    refresh,
  }), [organizations, activeId, problem, loading, generation, select, refresh]);

  return (
    <OrganizationContext.Provider value={value}>
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganization(): OrganizationState {
  const value = useContext(OrganizationContext);
  if (value === null) {
    throw new Error(
      'useOrganization must be used inside an OrganizationProvider.');
  }
  return value;
}

/** Human-readable explanation for each blocking state. */
export const PROBLEM_MESSAGE: Record<
  Exclude<OrganizationProblem, 'none'>, { title: string; body: string }
> = {
  no_memberships: {
    title: 'No workspace available',
    body: 'Your account is not a member of any organization yet. An '
      + 'administrator needs to add you before you can open a study.',
  },
  selection_required: {
    title: 'Choose an organization',
    body: 'You belong to more than one organization. Select the one you want '
      + 'to work in — nothing is chosen for you, because records are never '
      + 'shared between them.',
  },
  selection_unavailable: {
    title: 'That organization is no longer available',
    body: 'Your access to the previously selected organization has ended or '
      + 'been suspended. Choose another organization to continue.',
  },
  unavailable: {
    title: 'Cannot reach the service',
    body: 'The backend did not respond. This is a connection problem, not a '
      + 'permission problem — your access has not changed.',
  },
};
