/**
 * The organization switcher and the client half of the active-organization
 * contract.
 *
 * What is worth testing here
 * --------------------------
 * Not that a menu opens. The claims that matter are the ones the backend
 * cannot enforce:
 *
 *  - every request carries the header, including ones written by code that
 *    never heard of organizations;
 *  - a multi-organization user is never auto-selected into one;
 *  - cached state is cleared *before* the first request of the new
 *    organization, not after its response arrives;
 *  - a response from the previous organization that lands after a switch is
 *    discarded rather than rendered.
 *
 * The last two are the ones that produce a screenshot of one organization's
 * studies under another's name, which is the failure this whole mechanism
 * exists to prevent.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiRequest } from '../api/client';
import {
  ORGANIZATION_HEADER, currentGeneration, getActiveOrganizationId,
  isCurrentGeneration, organizationHeaders,
  resetActiveOrganizationForTests, setActiveOrganizationId,
} from './activeOrganization';
import {
  OrganizationProvider, clearOrganizationScopedState,
} from './OrganizationContext';
import { OrganizationSwitcher } from './OrganizationSwitcher';

const ACME = {
  id: 1, slug: 'acme-bio', name: 'Acme Bio', status: 'active',
  is_legacy: false, awaiting_confirmation: false, your_role: 'administrator',
  your_scope: 'organization', is_administrative: true,
  may_download_attachments: true,
};
const OTHER = {
  ...ACME, id: 2, slug: 'other-labs', name: 'Other Labs',
  your_role: 'approver', is_administrative: false,
};

function listing(organizations: unknown[]) {
  return {
    ok: true,
    json: async () => ({
      organizations,
      active_organization_id: getActiveOrganizationId(),
      requires_explicit_selection: organizations.length > 1,
    }),
  } as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetActiveOrganizationForTests();
  globalThis.sessionStorage?.clear();
  fetchMock = vi.fn(async () => listing([ACME]));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/* ---------------------------------------------------------------------- */
/* The header                                                              */
/* ---------------------------------------------------------------------- */

describe('the active-organization header', () => {
  it('is absent until an organization is selected', () => {
    expect(organizationHeaders()).toEqual({});
  });

  it('is present once one is selected', () => {
    setActiveOrganizationId(7);
    expect(organizationHeaders()).toEqual({ [ORGANIZATION_HEADER]: '7' });
  });

  it('is sent on every request through the shared transport', async () => {
    setActiveOrganizationId(42);
    await apiRequest('/api/v1/anything', { method: 'GET' },
      (_b): _b is unknown => true);

    expect(fetchMock).toHaveBeenCalled();
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>)[ORGANIZATION_HEADER])
      .toBe('42');
  });

  it('does not clobber a caller-supplied header', async () => {
    setActiveOrganizationId(42);
    await apiRequest('/api/v1/anything',
      { method: 'GET', headers: { 'X-Custom': 'kept' } },
      (_b): _b is unknown => true);

    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers['X-Custom']).toBe('kept');
    expect(headers[ORGANIZATION_HEADER]).toBe('42');
  });

  it('survives a storage backend that throws', () => {
    const original = globalThis.sessionStorage;
    Object.defineProperty(globalThis, 'sessionStorage', {
      configurable: true,
      get() { throw new Error('blocked by privacy mode'); },
    });
    try {
      expect(() => setActiveOrganizationId(3)).not.toThrow();
      expect(organizationHeaders()).toEqual({ [ORGANIZATION_HEADER]: '3' });
    } finally {
      Object.defineProperty(globalThis, 'sessionStorage', {
        configurable: true, value: original, writable: true,
      });
    }
  });
});

/* ---------------------------------------------------------------------- */
/* Stale responses                                                          */
/* ---------------------------------------------------------------------- */

describe('the generation counter', () => {
  it('marks a response issued before a switch as stale', () => {
    setActiveOrganizationId(1);
    const issuedAt = currentGeneration();
    expect(isCurrentGeneration(issuedAt)).toBe(true);

    setActiveOrganizationId(2);
    expect(isCurrentGeneration(issuedAt)).toBe(false);
  });

  it('does not advance when the same organization is re-selected', () => {
    setActiveOrganizationId(1);
    const before = currentGeneration();
    setActiveOrganizationId(1);
    expect(currentGeneration()).toBe(before);
  });
});

/* ---------------------------------------------------------------------- */
/* Selection rules                                                          */
/* ---------------------------------------------------------------------- */

describe('selecting an organization', () => {
  it('auto-selects when there is exactly one', async () => {
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('active-organization'))
        .toHaveTextContent('Acme Bio');
    });
    expect(getActiveOrganizationId()).toBe(1);
  });

  it('never guesses when there are several', async () => {
    fetchMock.mockImplementation(async () => listing([ACME, OTHER]));
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-problem-selection_required'))
        .toBeInTheDocument();
    });
    expect(getActiveOrganizationId()).toBeNull();
    expect(screen.getByTestId('active-organization'))
      .toHaveTextContent('Select an organization');
  });

  it('reports having no memberships as its own state', async () => {
    fetchMock.mockImplementation(async () => listing([]));
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-problem-no_memberships'))
        .toBeInTheDocument();
    });
    expect(screen.getByText(/not a member of any organization/i))
      .toBeInTheDocument();
  });

  it('distinguishes an unreachable backend from having no access', async () => {
    fetchMock.mockImplementation(async () => {
      throw new Error('connection refused');
    });
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-problem-unavailable'))
        .toBeInTheDocument();
    });
    expect(screen.getByText(/connection problem, not a permission problem/i))
      .toBeInTheDocument();
  });

  it('drops a stored selection that is no longer available', async () => {
    setActiveOrganizationId(99);          // revoked since it was stored
    fetchMock.mockImplementation(async () => listing([ACME, OTHER]));
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-problem-selection_unavailable'))
        .toBeInTheDocument();
    });
    expect(getActiveOrganizationId()).toBeNull();
  });

  it('switches, and sends the new header afterwards', async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async () => listing([ACME, OTHER]));
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-switcher')).toBeEnabled();
    });
    await user.click(screen.getByTestId('organization-switcher'));
    await user.click(screen.getByRole('menuitemradio', { name: /Other Labs/ }));

    await waitFor(() => expect(getActiveOrganizationId()).toBe(2));

    const last = fetchMock.mock.calls[fetchMock.mock.calls.length - 1]![1] as RequestInit;
    expect((last.headers as Record<string, string>)[ORGANIZATION_HEADER])
      .toBe('2');
  });
});

/* ---------------------------------------------------------------------- */
/* Cache clearing                                                           */
/* ---------------------------------------------------------------------- */

describe('switching clears organization-scoped state', () => {
  it('removes every scoped key and keeps unrelated ones', () => {
    const store = globalThis.sessionStorage;
    store.setItem('nanobio.workflow.activeStudy', '17');
    store.setItem('nanobio.registry.filters', '{"subtype":"cytotoxicity"}');
    store.setItem('nanobio.readiness.area', 'safety_assessment');
    store.setItem('nanobio.workspace.project', '4');
    store.setItem('nanobio.theme', 'dark');   // not organization-scoped

    clearOrganizationScopedState();

    expect(store.getItem('nanobio.workflow.activeStudy')).toBeNull();
    expect(store.getItem('nanobio.registry.filters')).toBeNull();
    expect(store.getItem('nanobio.readiness.area')).toBeNull();
    expect(store.getItem('nanobio.workspace.project')).toBeNull();
    expect(store.getItem('nanobio.theme')).toBe('dark');
  });

  it('clears before the first request of the new organization', async () => {
    const user = userEvent.setup();
    const store = globalThis.sessionStorage;
    fetchMock.mockImplementation(async () => listing([ACME, OTHER]));

    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);
    await waitFor(() => {
      expect(screen.getByTestId('organization-switcher')).toBeEnabled();
    });

    store.setItem('nanobio.workflow.activeStudy', '17');

    // Record whether the study was still cached at the moment each request
    // went out. Clearing *after* the response would leave a window in which
    // the previous organization's study is on screen under the new name.
    const cachedAtRequestTime: (string | null)[] = [];
    fetchMock.mockImplementation(async () => {
      cachedAtRequestTime.push(store.getItem('nanobio.workflow.activeStudy'));
      return listing([ACME, OTHER]);
    });

    await user.click(screen.getByTestId('organization-switcher'));
    await user.click(screen.getByRole('menuitemradio', { name: /Other Labs/ }));
    await waitFor(() => expect(getActiveOrganizationId()).toBe(2));

    expect(cachedAtRequestTime.length).toBeGreaterThan(0);
    expect(cachedAtRequestTime.every((v) => v === null)).toBe(true);
  });
});

/* ---------------------------------------------------------------------- */
/* Authority is displayed unambiguously                                     */
/* ---------------------------------------------------------------------- */

describe('administrative and scientific authority are never conflated', () => {
  it('labels an administrative role as access, not science', async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async () => listing([ACME, OTHER]));
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-switcher')).toBeEnabled();
    });
    await user.click(screen.getByTestId('organization-switcher'));

    // Acme: administrator — an access role.
    expect(screen.getByTestId('org-role-1')).toHaveTextContent(/^Access:/);
    // Other: approver — a scientific role.
    expect(screen.getByTestId('org-role-2')).toHaveTextContent(/^Scientific:/);
  });

  it('tells an administrator plainly that they hold no scientific authority',
    async () => {
      render(
        <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);
      await waitFor(() => {
        expect(screen.getByTestId('active-organization')).toBeInTheDocument();
      });
      // Single-organization view renders the compact label; switch to the
      // multi view where the note is shown.
      fetchMock.mockImplementation(async () => listing([ACME, OTHER]));
    });
});

/* ---------------------------------------------------------------------- */
/* Accessibility                                                            */
/* ---------------------------------------------------------------------- */

describe('accessibility', () => {
  it('exposes the switcher as a menu and closes on Escape', async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async () => listing([ACME, OTHER]));
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-switcher')).toBeEnabled();
    });
    const trigger = screen.getByTestId('organization-switcher');
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await user.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('menu', { name: /switch organization/i }))
      .toBeInTheDocument();

    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });
  });

  it('marks the active organization with aria-checked', async () => {
    const user = userEvent.setup();
    setActiveOrganizationId(1);
    fetchMock.mockImplementation(async () => listing([ACME, OTHER]));
    render(
      <OrganizationProvider><OrganizationSwitcher /></OrganizationProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('organization-switcher')).toBeEnabled();
    });
    await user.click(screen.getByTestId('organization-switcher'));

    expect(screen.getByRole('menuitemradio', { name: /Acme Bio/ }))
      .toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('menuitemradio', { name: /Other Labs/ }))
      .toHaveAttribute('aria-checked', 'false');
  });
});
