/**
 * The active organization, and the generation counter that makes switching safe.
 *
 * Why this is a module and not React state
 * ----------------------------------------
 * `apiRequest` in `api/client.ts` is a plain function, not a hook. Putting the
 * selection in React state would mean every call site had to read it from
 * context and pass it down — and the contract requires the header on *every*
 * request, including background polls and prefetches written by someone who
 * never read the contract.
 *
 * A module-level value that the transport reads directly means a call site
 * cannot forget it, because a call site never touches it.
 *
 * The generation counter
 * ----------------------
 * Switching organization does not cancel requests that are already in flight.
 * Those requests carry the *previous* header, so the backend correctly answers
 * them with the previous organization's data — and that answer arrives after
 * the interface has visually moved on.
 *
 * Every request records the generation it was issued in. On switch the counter
 * increments, and any response from an earlier generation is discarded rather
 * than rendered. This is the frontend half of the contract's "cancel or safely
 * disregard stale in-flight requests"; the backend half is that such a response
 * never contains a mixture of organizations.
 *
 * Persistence
 * -----------
 * The selection is kept in `sessionStorage`, not `localStorage`. Per tab, so
 * two tabs can genuinely be in two organizations; cleared when the tab closes,
 * so a shared machine does not hand the next person a pre-selected workspace.
 */

const STORAGE_KEY = 'nanobio.activeOrganizationId';

export const ORGANIZATION_HEADER = 'X-Organization-Id';

let activeOrganizationId: number | null = readStored();
let generation = 0;

type Listener = (id: number | null) => void;
const listeners = new Set<Listener>();

function readStored(): number | null {
  try {
    const raw = globalThis.sessionStorage?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    // sessionStorage throws in some privacy modes. An unavailable store is
    // not an error: it means "no selection", which is a valid state.
    return null;
  }
}

function writeStored(id: number | null): void {
  try {
    if (id === null) globalThis.sessionStorage?.removeItem(STORAGE_KEY);
    else globalThis.sessionStorage?.setItem(STORAGE_KEY, String(id));
  } catch {
    /* see readStored */
  }
}

export function getActiveOrganizationId(): number | null {
  return activeOrganizationId;
}

/** The generation a request should record when it is issued. */
export function currentGeneration(): number {
  return generation;
}

/** Is a response from `issuedAt` still worth rendering? */
export function isCurrentGeneration(issuedAt: number): boolean {
  return issuedAt === generation;
}

/**
 * Select an organization, or clear the selection.
 *
 * Increments the generation *before* notifying listeners, so any request a
 * listener issues in response belongs to the new generation, and every
 * response still outstanding from the old one is already stale.
 */
export function setActiveOrganizationId(id: number | null): void {
  if (id === activeOrganizationId) return;
  activeOrganizationId = id;
  generation += 1;
  writeStored(id);
  for (const listener of listeners) listener(id);
}

export function subscribeToActiveOrganization(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Headers to merge into a request. Empty when nothing is selected.
 *
 * Omitting the header means "all my organizations", which is the correct
 * behaviour before a choice has been made and the only safe default: sending
 * a guessed identifier would be the frontend deciding something the contract
 * says the user must decide.
 */
export function organizationHeaders(): Record<string, string> {
  return activeOrganizationId === null
    ? {}
    : { [ORGANIZATION_HEADER]: String(activeOrganizationId) };
}

/** Test seam. Resets module state between cases. */
export function resetActiveOrganizationForTests(): void {
  activeOrganizationId = null;
  generation = 0;
  listeners.clear();
  writeStored(null);
}
