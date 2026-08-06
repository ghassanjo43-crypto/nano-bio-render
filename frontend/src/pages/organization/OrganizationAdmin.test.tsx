/**
 * The organization management screens.
 *
 * What is worth testing here
 * --------------------------
 * Not that a table renders. The claims that matter are the ones a screenshot
 * would not catch:
 *
 *  - organization authority and scientific assignment are shown as two
 *    distinct things, in words, so "Administrator" cannot be read as "can
 *    approve";
 *  - the controls that would let somebody escalate — changing your own role,
 *    removing the last owner — are not offered, and the reason is shown in
 *    their place;
 *  - every action that ends somebody's access requires the subject's name to
 *    be typed, so a mis-click on a list of similar rows cannot do it;
 *  - the study-team role menu is built from what the backend says the person
 *    is eligible for, never from a client-side copy of the rule;
 *  - no password is displayed, requested or transmitted anywhere;
 *  - a response that arrives after an organization switch is discarded rather
 *    than rendered under the new organization's name.
 *
 * Every negative assertion has a positive control nearby. "The remove button
 * is absent for the last owner" proves nothing if the button is absent for
 * everybody.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../../auth/AuthContext';
import {
  resetActiveOrganizationForTests, setActiveOrganizationId,
} from '../../organizations/activeOrganization';
import { OrganizationProvider } from '../../organizations/OrganizationContext';
import OrganizationAdminPage from './OrganizationAdminPage';
import StudyTeamPage from './StudyTeamPage';
import AcceptInvitationPage from './AcceptInvitationPage';

/* ---------------------------------------------------------------------- */
/* Fixtures                                                                */
/* ---------------------------------------------------------------------- */

const ORGANIZATION = {
  id: 1, slug: 'acme-bio', name: 'Acme Bio', description: null,
  status: 'active', is_legacy: false, awaiting_confirmation: false,
  confirmed_at: null, created_at: '2026-01-01T00:00:00Z',
  your_role: 'owner', your_scope: 'organization', is_administrative: true,
  may_download_attachments: true,
  capabilities: {
    manage_organization: true, manage_members: true,
    manage_assignments: true, view_access_history: true,
  },
};

function member(overrides: Record<string, unknown> = {}) {
  return {
    id: 10, user_id: 100, username: 'rosalind', role: 'researcher',
    is_administrative: false, scope: 'assigned_studies', status: 'active',
    is_active: true, starts_at: null, expires_at: null,
    external_organization: null, is_external: false,
    may_download_attachments: true, created_at: '2026-01-01T00:00:00Z',
    ended_at: null, end_reason: null, revision: 3,
    assignable_study_roles: ['contributor', 'study_owner', 'auditor'],
    ...overrides,
  };
}

const OWNER = member({
  id: 11, user_id: 101, username: 'dorothy', role: 'owner',
  is_administrative: true, scope: 'organization',
  assignable_study_roles: ['auditor'], revision: 1,
});
const ADMIN = member({
  id: 12, user_id: 102, username: 'ada', role: 'administrator',
  is_administrative: true, scope: 'organization',
  assignable_study_roles: ['auditor'], revision: 1,
});
const APPROVER = member({
  id: 13, user_id: 103, username: 'barbara', role: 'approver',
  assignable_study_roles: ['approver', 'reviewer', 'auditor'], revision: 1,
});
const CRO = member({
  id: 14, user_id: 104, username: 'contract-lab', role: 'lab_contributor',
  external_organization: 'Contract Labs Ltd', is_external: true,
  may_download_attachments: false,
  expires_at: '2026-12-31T00:00:00Z',
  assignable_study_roles: ['lab_contributor'], revision: 1,
});

const ROSALIND = member();

let fetchMock: ReturnType<typeof vi.fn>;
/** Requests observed, so a test can assert what was sent. */
let calls: Array<{ url: string; init: RequestInit | undefined }>;

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

/**
 * One router for every organization endpoint the screens touch.
 *
 * Deliberately keyed on method AND path: several tests turn on the difference
 * between a read and the write that followed it.
 */
function route(url: string, init?: RequestInit): unknown {
  const method = (init?.method ?? 'GET').toUpperCase();

  if (url.endsWith('/api/v1/auth/me')) {
    return {
      id: 101, username: 'dorothy', role: 'admin', is_active: true,
    };
  }
  if (url.endsWith('/api/v1/organizations')) {
    return {
      organizations: [{
        id: 1, slug: 'acme-bio', name: 'Acme Bio', status: 'active',
        is_legacy: false, awaiting_confirmation: false, your_role: 'owner',
        your_scope: 'organization', is_administrative: true,
        may_download_attachments: true,
      }],
      active_organization_id: 1,
      requires_explicit_selection: false,
    };
  }
  if (url.endsWith('/api/v1/organizations/1')) return ORGANIZATION;
  if (url.endsWith('/members')) {
    return {
      organization_id: 1,
      members: [OWNER, ADMIN, ROSALIND, APPROVER, CRO],
    };
  }
  if (url.endsWith('/collaborators')) {
    return {
      organization_id: 1, collaborators: [CRO],
      notice: 'External collaborators reach only assigned studies.',
    };
  }
  if (url.includes('/invitations/accept')) {
    return {
      organization_id: 1, membership_id: 20, role: 'researcher',
      is_administrative: false, expires_at: null,
      notice: 'You are now a member of this organization. This grants no '
        + 'scientific authority on any study.',
    };
  }
  if (url.includes('/invitations') && method === 'GET') {
    return {
      organization_id: 1, invitations: [], delivery_provider: 'recorded',
    };
  }
  if (url.includes('/invitations') && method === 'POST') {
    return {
      id: 55, organization_id: 1, email: 'newcomer@acme.test',
      role: 'researcher', scope: 'assigned_studies', status: 'pending',
      is_administrative: false, token_prefix: 'abcd1234',
      expires_at: '2026-08-10T00:00:00Z', membership_expires_at: null,
      external_organization: null, is_external: false,
      may_download_attachments: true, delivery_provider: 'recorded',
      delivery_status: 'recorded',
      delivery_detail: 'No delivery service is configured.',
      created_at: '2026-08-03T00:00:00Z', accepted_at: null,
      ended_at: null, end_reason: null,
      invitation_link: '/invitations/accept?token=one-time-value',
      link_shown_once: true,
      notice: 'This link is shown once and cannot be retrieved again.',
    };
  }
  if (url.endsWith('/team/history')) {
    return {
      study_id: 7,
      events: [{
        id: 1, event: 'assignment_created', subject_type: 'study_assignment',
        subject_id: 9, actor_username: 'dorothy',
        summary: 'dorothy assigned user #103 as approver on study #7.',
        created_at: '2026-08-01T09:00:00Z',
      }],
    };
  }
  if (url.endsWith('/team') && method === 'GET') {
    return {
      study_id: 7,
      assignments: [{
        id: 9, user_id: 103, username: 'barbara', study_id: 7,
        role: 'approver', status: 'active', is_active: true,
        starts_at: null, expires_at: '2026-12-01T00:00:00Z',
        may_download_attachments: null, note: 'Protocol P-14.',
        permitted_subtypes: null, created_at: '2026-08-01T09:00:00Z',
        ended_at: null, end_reason: null, revision: 2,
      }],
    };
  }
  if (url.endsWith('/team') && method === 'POST') {
    return {
      id: 12, user_id: 100, username: 'rosalind', study_id: 7,
      role: 'contributor', status: 'active', is_active: true,
      starts_at: null, expires_at: null, may_download_attachments: null,
      note: null, permitted_subtypes: null,
      created_at: '2026-08-03T00:00:00Z', ended_at: null, end_reason: null,
      revision: 1,
    };
  }
  if (url.includes('/audit')) {
    return {
      organization_id: 1, append_only: true,
      events: [{
        id: 2, event: 'member_revoked', subject_type: 'membership',
        subject_id: 10, actor_username: 'dorothy',
        summary: 'dorothy revoked access for user #100.',
        created_at: '2026-08-02T12:00:00Z',
      }],
    };
  }
  // Writes the tests do not care about the body of.
  return { ...ROSALIND, status: 'revoked', is_active: false };
}

beforeEach(() => {
  resetActiveOrganizationForTests();
  globalThis.sessionStorage?.clear();
  setActiveOrganizationId(1);
  calls = [];
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return jsonResponse(route(url, init));
  });
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderAdmin() {
  return render(
    <MemoryRouter initialEntries={['/organization']}>
      <AuthProvider>
        <OrganizationProvider>
          <Routes>
            <Route path="/organization" element={<OrganizationAdminPage />} />
          </Routes>
        </OrganizationProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function openTab(name: RegExp) {
  const user = userEvent.setup();
  await waitFor(() =>
    expect(screen.getByRole('tab', { name })).toBeInTheDocument());
  await user.click(screen.getByRole('tab', { name }));
  return user;
}

/* ====================================================================== */
/* 1. Authority is never one column                                        */
/* ====================================================================== */

describe('organization authority versus scientific assignment', () => {
  it('names the kind of authority in words, not only in colour', async () => {
    renderAdmin();
    await waitFor(() =>
      expect(screen.getByTestId('authority-legend')).toBeInTheDocument());

    const legend = screen.getByTestId('authority-legend');
    expect(within(legend).getAllByText(/Organization authority/).length)
      .toBeGreaterThan(0);
    expect(within(legend).getAllByText(/Scientific eligibility/).length)
      .toBeGreaterThan(0);
    expect(legend.textContent).toMatch(/cannot.*approve/i);
  });

  it('labels an administrator as authority and an approver as scientific',
    async () => {
      renderAdmin();
      await openTab(/Members/);

      await waitFor(() =>
        expect(screen.getByTestId('member-role-ada')).toBeInTheDocument());

      expect(screen.getByTestId('member-role-ada').textContent)
        .toMatch(/Organization authority/);
      expect(screen.getByTestId('member-role-barbara').textContent)
        .toMatch(/Scientific eligibility/);
    });

  it('never presents administrator and approver in the same vocabulary',
    async () => {
      renderAdmin();
      await openTab(/Members/);
      await waitFor(() =>
        expect(screen.getByTestId('member-role-ada')).toBeInTheDocument());

      const admin = screen.getByTestId('member-role-ada').textContent ?? '';
      const approver =
        screen.getByTestId('member-role-barbara').textContent ?? '';
      expect(admin).not.toEqual(approver);
      expect(admin).not.toMatch(/Scientific/);
      expect(approver).not.toMatch(/Organization authority/);
    });
});

/* ====================================================================== */
/* 2. Escalation controls are not offered                                  */
/* ====================================================================== */

describe('self-escalation', () => {
  it('offers no control to change your own role, and says why', async () => {
    renderAdmin();
    await openTab(/Members/);

    await waitFor(() =>
      expect(screen.getByTestId('member-dorothy')).toBeInTheDocument());

    // dorothy is the signed-in user in this fixture.
    const own = screen.getByTestId('self-locked-dorothy');
    expect(own.textContent).toMatch(/cannot change your own role/i);
    expect(own.textContent).toMatch(/another owner or administrator/i);
    expect(screen.queryByTestId('remove-dorothy')).toBeNull();
  });

  it('offers the same controls for somebody else', async () => {
    renderAdmin();
    await openTab(/Members/);
    await waitFor(() =>
      expect(screen.getByTestId('remove-rosalind')).toBeInTheDocument());
    expect(screen.getByTestId('suspend-rosalind')).toBeInTheDocument();
  });
});

/* ====================================================================== */
/* 3. Last-owner protection                                               */
/* ====================================================================== */

describe('the last active owner', () => {
  it('explains why the owner cannot be removed when there is only one',
    async () => {
      fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
        calls.push({ url, init });
        if (url.endsWith('/members')) {
          return jsonResponse({
            organization_id: 1, members: [OWNER, ADMIN, ROSALIND],
          });
        }
        return jsonResponse(route(url, init));
      });

      renderAdmin();
      await openTab(/Members/);

      await waitFor(() =>
        expect(screen.getByText(/One active owner/)).toBeInTheDocument());
      expect(screen.getByText(/Appoint a second owner/)).toBeVisible();
      // Positive control: an ordinary member is still removable.
      expect(screen.getByTestId('remove-rosalind')).toBeEnabled();
    });
});

/* ====================================================================== */
/* 4. Sensitive actions require the subject to be named                    */
/* ====================================================================== */

describe('confirmation of sensitive actions', () => {
  it('will not remove a member until their name is typed', async () => {
    renderAdmin();
    const user = await openTab(/Members/);

    await waitFor(() =>
      expect(screen.getByTestId('remove-rosalind')).toBeInTheDocument());
    await user.click(screen.getByTestId('remove-rosalind'));

    const confirm = await screen.findByTestId('confirm-revoke-confirm');
    expect(confirm).toBeDisabled();

    // Naming somebody else does not arm it.
    await user.type(screen.getByLabelText(/Type rosalind to confirm/), 'ada');
    expect(confirm).toBeDisabled();

    await user.clear(screen.getByLabelText(/Type rosalind to confirm/));
    await user.type(screen.getByLabelText(/Type rosalind to confirm/),
                    'rosalind');
    expect(confirm).toBeEnabled();
  });

  it('states that removal preserves historical attribution', async () => {
    renderAdmin();
    const user = await openTab(/Members/);
    await waitFor(() =>
      expect(screen.getByTestId('remove-rosalind')).toBeInTheDocument());
    await user.click(screen.getByTestId('remove-rosalind'));

    const dialog = await screen.findByTestId('confirm-revoke');
    expect(dialog.textContent).toMatch(/not deleted or reattributed/i);
  });

  it('sends the revision it read, so a stale screen cannot overwrite',
    async () => {
      renderAdmin();
      const user = await openTab(/Members/);
      await waitFor(() =>
        expect(screen.getByTestId('remove-rosalind')).toBeInTheDocument());
      await user.click(screen.getByTestId('remove-rosalind'));
      await user.type(screen.getByLabelText(/Type rosalind to confirm/),
                      'rosalind');
      await user.click(screen.getByTestId('confirm-revoke-confirm'));

      await waitFor(() => {
        const write = calls.find(
          (c) => (c.init?.method ?? '').toUpperCase() === 'DELETE');
        expect(write).toBeTruthy();
        expect(JSON.parse(String(write?.init?.body)))
          .toMatchObject({ expected_revision: ROSALIND.revision });
      });
    });
});

/* ====================================================================== */
/* 5. No credentials anywhere                                             */
/* ====================================================================== */

describe('credentials', () => {
  it('offers no password field on any management screen', async () => {
    const { container } = renderAdmin();
    for (const tab of [/Profile/, /Members/, /Invitations/,
                       /External collaborators/, /Access history/]) {
      await openTab(tab);
      await waitFor(() =>
        expect(container.querySelectorAll('input[type="password"]'))
          .toHaveLength(0));
      expect(screen.queryByLabelText(/password/i)).toBeNull();
    }
  });

  it('sends no password field when inviting somebody', async () => {
    renderAdmin();
    const user = await openTab(/Invitations/);

    await waitFor(() =>
      expect(screen.getByTestId('send-invitation')).toBeInTheDocument());
    await user.type(screen.getByLabelText(/Email address/),
                    'newcomer@acme.test');
    await user.click(screen.getByTestId('send-invitation'));

    await waitFor(() => {
      const write = calls.find(
        (c) => c.url.includes('/invitations')
          && (c.init?.method ?? '').toUpperCase() === 'POST');
      expect(write).toBeTruthy();
      const body = JSON.parse(String(write?.init?.body));
      expect(Object.keys(body)).not.toContain('password');
      expect(JSON.stringify(body)).not.toMatch(/password/i);
    });
  });
});

/* ====================================================================== */
/* 6. Invitations                                                          */
/* ====================================================================== */

describe('invitations', () => {
  it('says plainly that nothing is emailed when no provider is configured',
    async () => {
      renderAdmin();
      await openTab(/Invitations/);
      await waitFor(() => expect(
        screen.getByText(/No delivery service is configured/))
        .toBeInTheDocument());
    });

  it('shows the one-time link and says it cannot be retrieved again',
    async () => {
      renderAdmin();
      const user = await openTab(/Invitations/);
      await waitFor(() =>
        expect(screen.getByTestId('send-invitation')).toBeInTheDocument());
      await user.type(screen.getByLabelText(/Email address/),
                      'newcomer@acme.test');
      await user.click(screen.getByTestId('send-invitation'));

      const link = await screen.findByTestId('invitation-link');
      expect(link.textContent).toContain('token=one-time-value');
      expect(screen.getByText(/shown once and cannot be retrieved/i))
        .toBeVisible();
    });

  it('explains that an organization role is not a study assignment',
    async () => {
      renderAdmin();
      await openTab(/Invitations/);
      await waitFor(() => expect(
        screen.getByLabelText(/Organization role/)).toBeInTheDocument());
      const help = screen.getByLabelText(/Organization role/)
        .closest('.ds-field')?.textContent ?? '';
      expect(help).toMatch(/never assigns them to a study/i);
    });
});

/* ====================================================================== */
/* 7. External collaborators                                              */
/* ====================================================================== */

describe('external collaborators', () => {
  it('lists only external memberships and shows the access window',
    async () => {
      renderAdmin();
      await openTab(/External collaborators/);

      await waitFor(() => expect(
        screen.getByTestId('collaborator-contract-lab')).toBeInTheDocument());
      // Positive control is the presence of the CRO; the claim is the absence
      // of everybody else.
      expect(screen.queryByTestId('collaborator-dorothy')).toBeNull();
      expect(screen.getByTestId('collaborator-contract-lab').textContent)
        .toMatch(/Contract Labs Ltd/);
    });

  it('shows an attachment prohibition as a distinct state', async () => {
    renderAdmin();
    await openTab(/External collaborators/);
    await waitFor(() => expect(
      screen.getByTestId('collaborator-contract-lab')).toBeInTheDocument());
    expect(screen.getByText(/Downloads withheld/)).toBeVisible();
  });

  it('states that expiry is evaluated on every request', async () => {
    renderAdmin();
    await openTab(/External collaborators/);
    await waitFor(() =>
      expect(screen.getByText(/every request/i)).toBeInTheDocument());
  });
});

/* ====================================================================== */
/* 8. Access history                                                       */
/* ====================================================================== */

describe('access history', () => {
  it('renders the trail and says it is append-only', async () => {
    renderAdmin();
    await openTab(/Access history/);
    await waitFor(() =>
      expect(screen.getByTestId('audit-table')).toBeInTheDocument());
    expect(screen.getByText(/append-only/i)).toBeVisible();
    expect(screen.getByText(/revoked access for user/)).toBeVisible();
  });

  it('explains the refusal rather than showing an empty table when the role '
    + 'may not read it', async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith('/api/v1/organizations/1')) {
        return jsonResponse({
          ...ORGANIZATION,
          capabilities: { ...ORGANIZATION.capabilities,
                          view_access_history: false },
        });
      }
      return jsonResponse(route(url, init));
    });

    renderAdmin();
    await openTab(/Access history/);
    await waitFor(() => expect(
      screen.getByText(/Not available to this role/)).toBeInTheDocument());
    expect(screen.queryByTestId('audit-table')).toBeNull();
  });
});

/* ====================================================================== */
/* 9. Migrated-organization confirmation                                   */
/* ====================================================================== */

describe('confirming a migrated organization', () => {
  function renderPending() {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith('/api/v1/organizations/1')) {
        return jsonResponse({
          ...ORGANIZATION, status: 'pending_confirmation',
          is_legacy: true, awaiting_confirmation: true,
        });
      }
      return jsonResponse(route(url, init));
    });
    return renderAdmin();
  }

  it('states that confirming grants nobody scientific authority', async () => {
    renderPending();
    await waitFor(() => expect(
      screen.getByTestId('confirm-organization')).toBeInTheDocument());
    expect(screen.getByText(/grants nobody scientific authority/i))
      .toBeVisible();
    expect(screen.getByText(/appointed explicitly/i)).toBeVisible();
  });

  it('requires the organization identifier to be typed', async () => {
    const user = userEvent.setup();
    renderPending();
    await waitFor(() => expect(
      screen.getByTestId('confirm-organization')).toBeInTheDocument());
    await user.click(screen.getByTestId('confirm-organization'));

    const submit = screen.getByTestId('confirm-organization-submit');
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText(/Type acme-bio to confirm/),
                    'acme-bio');
    expect(submit).toBeEnabled();
  });
});

/* ====================================================================== */
/* 10. The study team                                                      */
/* ====================================================================== */

function renderTeam() {
  return render(
    <MemoryRouter initialEntries={['/organization/studies/7/team']}>
      <AuthProvider>
        <OrganizationProvider>
          <Routes>
            <Route path="/organization/studies/:studyId/team"
                   element={<StudyTeamPage />} />
          </Routes>
        </OrganizationProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('the study team', () => {
  it('states the appointment-authority rule on the screen', async () => {
    renderTeam();
    await waitFor(() => expect(
      screen.getByText(/Who may appoint/)).toBeInTheDocument());
    expect(screen.getByText(/nobody may change their own organization role/i))
      .toBeVisible();
    expect(screen.getByText(/two acts by two different people/i)).toBeVisible();
  });

  it('offers only the study roles the backend says the person is eligible for',
    async () => {
      const user = userEvent.setup();
      renderTeam();

      await waitFor(() => expect(
        screen.getByLabelText(/^Person$/)).toBeInTheDocument());
      await user.selectOptions(screen.getByLabelText(/^Person$/), '100');

      const roleSelect = screen.getByLabelText(/Scientific role on this study/);
      const offered = within(roleSelect).getAllByRole('option')
        .map((o) => (o as HTMLOptionElement).value)
        .filter(Boolean);

      // rosalind is an organization researcher.
      expect(offered.sort())
        .toEqual(['auditor', 'contributor', 'study_owner']);
      expect(offered).not.toContain('approver');
      expect(offered).not.toContain('reviewer');
    });

  it('offers approver for somebody the backend says is eligible', async () => {
    const user = userEvent.setup();
    renderTeam();
    await waitFor(() => expect(
      screen.getByLabelText(/^Person$/)).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText(/^Person$/), '103');

    const roleSelect = screen.getByLabelText(/Scientific role on this study/);
    const offered = within(roleSelect).getAllByRole('option')
      .map((o) => (o as HTMLOptionElement).value).filter(Boolean);
    expect(offered).toContain('approver');
  });

  it('offers only auditor for an administrator', async () => {
    const user = userEvent.setup();
    renderTeam();
    await waitFor(() => expect(
      screen.getByLabelText(/^Person$/)).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText(/^Person$/), '102');

    const roleSelect = screen.getByLabelText(/Scientific role on this study/);
    const offered = within(roleSelect).getAllByRole('option')
      .map((o) => (o as HTMLOptionElement).value).filter(Boolean);
    expect(offered).toEqual(['auditor']);
  });

  it('sends a withheld attachment flag as a restriction and never as a grant',
    async () => {
      const user = userEvent.setup();
      renderTeam();
      await waitFor(() => expect(
        screen.getByLabelText(/^Person$/)).toBeInTheDocument());
      await user.selectOptions(screen.getByLabelText(/^Person$/), '100');
      await user.selectOptions(
        screen.getByLabelText(/Scientific role on this study/), 'contributor');
      await user.click(screen.getByTestId('team-withhold-downloads'));
      await user.click(screen.getByTestId('appoint-to-study'));

      await waitFor(() => {
        const write = calls.find(
          (c) => c.url.endsWith('/team')
            && (c.init?.method ?? '').toUpperCase() === 'POST');
        expect(write).toBeTruthy();
        expect(JSON.parse(String(write?.init?.body)))
          .toMatchObject({ may_download_attachments: false });
      });
    });

  it('sends null rather than true when downloads are not withheld',
    async () => {
      const user = userEvent.setup();
      renderTeam();
      await waitFor(() => expect(
        screen.getByLabelText(/^Person$/)).toBeInTheDocument());
      await user.selectOptions(screen.getByLabelText(/^Person$/), '100');
      await user.selectOptions(
        screen.getByLabelText(/Scientific role on this study/), 'contributor');
      await user.click(screen.getByTestId('appoint-to-study'));

      await waitFor(() => {
        const write = calls.find(
          (c) => c.url.endsWith('/team')
            && (c.init?.method ?? '').toUpperCase() === 'POST');
        expect(JSON.parse(String(write?.init?.body)).may_download_attachments)
          .toBeNull();
      });
    });

  it('requires the person to be named before revoking an assignment',
    async () => {
      const user = userEvent.setup();
      renderTeam();
      await waitFor(() => expect(
        screen.getByTestId('revoke-assignment-9')).toBeInTheDocument());
      await user.click(screen.getByTestId('revoke-assignment-9'));

      const confirm = await screen.findByTestId(
        'confirm-revoke-assignment-confirm');
      expect(confirm).toBeDisabled();
      expect(screen.getByTestId('confirm-revoke-assignment').textContent)
        .toMatch(/Historical attribution is unchanged/i);

      await user.type(screen.getByLabelText(/Type barbara to confirm/),
                      'barbara');
      expect(confirm).toBeEnabled();
    });

  it('shows the assignment and revocation history', async () => {
    renderTeam();
    await waitFor(() => expect(
      screen.getByTestId('team-history-table')).toBeInTheDocument());
    expect(screen.getByText(/assigned user #103 as approver/)).toBeVisible();
  });
});

/* ====================================================================== */
/* 11. Accepting an invitation                                            */
/* ====================================================================== */

describe('accepting an invitation', () => {
  function renderAccept(search: string) {
    return render(
      <MemoryRouter initialEntries={[`/invitations/accept${search}`]}>
        <AuthProvider>
          <OrganizationProvider>
            <Routes>
              <Route path="/invitations/accept"
                     element={<AcceptInvitationPage />} />
            </Routes>
          </OrganizationProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
  }

  it('sends only the token, never a redirect target', async () => {
    const user = userEvent.setup();
    renderAccept('?token=one-time-value&next=https://evil.example/steal');

    await waitFor(() => expect(
      screen.getByTestId('accept-invitation')).toBeInTheDocument());
    await user.click(screen.getByTestId('accept-invitation'));

    await waitFor(() => {
      const write = calls.find((c) => c.url.includes('/invitations/accept'));
      expect(write).toBeTruthy();
      const body = JSON.parse(String(write?.init?.body));
      expect(body).toEqual({ token: 'one-time-value' });
      expect(JSON.stringify(body)).not.toMatch(/evil\.example/);
    });
  });

  it('says that joining grants no scientific authority', async () => {
    const user = userEvent.setup();
    renderAccept('?token=one-time-value');
    await waitFor(() => expect(
      screen.getByTestId('accept-invitation')).toBeInTheDocument());
    await user.click(screen.getByTestId('accept-invitation'));

    await waitFor(() => expect(
      screen.getByTestId('invitation-accepted')).toBeInTheDocument());
    expect(screen.getByTestId('invitation-accepted').textContent)
      .toMatch(/no scientific authority/i);
  });

  it('reports every failure identically', async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.includes('/invitations/accept')) {
        return jsonResponse(
          { error: 'not_found', message: 'No such invitation.' }, false, 404);
      }
      return jsonResponse(route(url, init));
    });

    const user = userEvent.setup();
    renderAccept('?token=whatever-this-is');
    await waitFor(() => expect(
      screen.getByTestId('accept-invitation')).toBeInTheDocument());
    await user.click(screen.getByTestId('accept-invitation'));

    const error = await screen.findByTestId('invitation-error');
    // No cause is named: "expired" would confirm the token was real.
    expect(error.textContent).toMatch(/cannot be used/i);
    expect(error.textContent).not.toMatch(/expired/i);
    expect(error.textContent).not.toMatch(/revoked/i);
  });

  it('refuses to act without a token', async () => {
    renderAccept('');
    await waitFor(() => expect(
      screen.getByText(/No invitation token/)).toBeInTheDocument());
    expect(screen.getByTestId('accept-invitation')).toBeDisabled();
  });
});

/* ====================================================================== */
/* 12. Cache and stale-request isolation across a switch                    */
/* ====================================================================== */

describe('switching organization', () => {
  it('discards a members response that arrives after the switch', async () => {
    // The failure this guards against: the previous organization's members
    // rendered under the new organization's name, for as long as the slow
    // response takes to arrive.
    // A deferred, written so TypeScript can see the resolver is assigned.
    // `let x: (() => void) | null` narrows to `never` after the executor,
    // because the compiler does not model synchronous executor calls.
    let releaseSlowMembers!: () => void;
    const slow = new Promise<void>((resolve) => { releaseSlowMembers = resolve; });
    let membersRequests = 0;

    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith('/members')) {
        membersRequests += 1;
        if (membersRequests === 1) {
          await slow;
          return jsonResponse({
            organization_id: 1,
            members: [member({ username: 'previous-org-person' })],
          });
        }
        return jsonResponse({
          organization_id: 2,
          members: [member({ id: 90, user_id: 900,
                             username: 'new-org-person' })],
        });
      }
      return jsonResponse(route(url, init));
    });

    renderAdmin();
    await openTab(/Members/);
    await waitFor(() => expect(membersRequests).toBe(1));

    // Switch while the first request is still outstanding.
    setActiveOrganizationId(2);

    await waitFor(() => expect(membersRequests).toBe(2));
    await waitFor(() => expect(
      screen.getByTestId('member-new-org-person')).toBeInTheDocument());

    // Now let the previous organization's response land.
    releaseSlowMembers();

    await waitFor(() => expect(
      screen.getByTestId('member-new-org-person')).toBeInTheDocument());
    expect(screen.queryByTestId('member-previous-org-person')).toBeNull();
  });

  it('clears the previous organization before the new request resolves',
    async () => {
      let releaseSecond!: () => void;
      const held = new Promise<void>((resolve) => { releaseSecond = resolve; });
      let membersRequests = 0;

      fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
        calls.push({ url, init });
        if (url.endsWith('/members')) {
          membersRequests += 1;
          if (membersRequests > 1) await held;
          return jsonResponse({
            organization_id: 1,
            members: [member({ username: 'first-org-person' })],
          });
        }
        return jsonResponse(route(url, init));
      });

      renderAdmin();
      await openTab(/Members/);
      await waitFor(() => expect(
        screen.getByTestId('member-first-org-person')).toBeInTheDocument());

      setActiveOrganizationId(2);

      // The old rows are gone immediately, not when the new response lands.
      await waitFor(() =>
        expect(screen.queryByTestId('member-first-org-person')).toBeNull());

      releaseSecond();
    });
});

/* ====================================================================== */
/* 13. Blocking organization states                                         */
/* ====================================================================== */

describe('organization states the screens must handle', () => {
  it('reports no memberships as a state, not as an error', async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith('/api/v1/organizations')) {
        return jsonResponse({
          organizations: [], active_organization_id: null,
          requires_explicit_selection: false,
        });
      }
      return jsonResponse(route(url, init));
    });

    renderAdmin();
    await waitFor(() => expect(
      screen.getByTestId('organization-problem-no_memberships'))
      .toBeInTheDocument());
    expect(screen.getByText(/administrator needs to add you/i)).toBeVisible();
  });

  it('distinguishes an unreachable backend from a lack of access', async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith('/api/v1/organizations')) {
        return jsonResponse({ error: 'boom', message: 'nope' }, false, 500);
      }
      return jsonResponse(route(url, init));
    });

    renderAdmin();
    await waitFor(() => expect(
      screen.getByTestId('organization-problem-unavailable'))
      .toBeInTheDocument());
    expect(screen.getByText(/not a permission problem/i)).toBeVisible();
  });
});
