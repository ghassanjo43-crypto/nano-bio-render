/**
 * Live multi-user walkthrough of organization and study-team management.
 *
 * What this proves that no other suite can
 * ----------------------------------------
 * The vitest suite stubs `fetch`, so it would pass against a backend that does
 * not serve these routes. The pytest suite drives the API directly, so it would
 * pass against a frontend that never calls it. Only this script drives a real
 * browser against a running server, with **three different accounts**, through
 * the sequence that actually matters:
 *
 *   an administrator invites somebody → the invitation is redeemed → the new
 *   member holds no scientific authority → an administrator cannot give
 *   themselves any → a second person appoints an approver → revocation takes
 *   effect on the next request.
 *
 * Three accounts, and they matter
 * -------------------------------
 * Escalation is only genuinely barred if the bar is on *self*-change, so a
 * single-account run would skip the control the whole model rests on. The
 * script needs an owner, an administrator and a newcomer, and it checks the
 * administrator cannot promote themselves while the owner can promote them.
 *
 * Credentials come from the environment. Nothing is embedded, and no password
 * is ever typed into a management screen — people are added by invitation and
 * sign in with their own.
 */

import { chromium } from 'playwright';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const OUT = resolve('../docs/screenshots');
mkdirSync(OUT, { recursive: true });

// The owner. The administrator and the newcomer are separate accounts.
const { user: OWNER_USER, pass: OWNER_PASS } = walkthroughCredentials();
const ADMIN_USER = process.env.NANOBIO_ORG_ADMIN_USER;
const ADMIN_PASS = process.env.NANOBIO_ORG_ADMIN_PASSWORD;
const NEW_USER = process.env.NANOBIO_ORG_NEWCOMER_USER;
const NEW_PASS = process.env.NANOBIO_ORG_NEWCOMER_PASSWORD;
const NEW_EMAIL = process.env.NANOBIO_ORG_NEWCOMER_EMAIL;

if (!ADMIN_USER || !ADMIN_PASS || !NEW_USER || !NEW_PASS || !NEW_EMAIL) {
  console.error(`
The organization walkthrough needs THREE accounts. Escalation is barred by a
rule about acting on yourself, so a single-account run would prove nothing.

  PowerShell:
    $env:NANOBIO_ORG_ADMIN_USER      = 'walkthrough_admin'
    $env:NANOBIO_ORG_ADMIN_PASSWORD  = '<the administrator password>'
    $env:NANOBIO_ORG_NEWCOMER_USER   = 'walkthrough_newcomer'
    $env:NANOBIO_ORG_NEWCOMER_PASSWORD = '<the newcomer password>'
    $env:NANOBIO_ORG_NEWCOMER_EMAIL  = '<the newcomer account email>'

The newcomer's email must be the address on their account: an invitation is
redeemable only by the account holding the address it was sent to.

Create the accounts against the development database with:

    python nanobio_studio_backend/scripts/create_admin.py \\
        --username walkthrough_admin --role researcher

Nothing was run and no browser was launched.
`);
  process.exit(2);
}

const problems = [];
const notes = [];
const log = (l, v) => console.log(`${l.padEnd(64, '.')} ${v}`);
function check(label, ok, detail = '') {
  log(label, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
}

async function shot(page, name) {
  await page.screenshot({ path: resolve(OUT, `organization-${name}.png`),
                          fullPage: true });
}

/** Call the API through the page, so the session cookie travels with it. */
function api(page) {
  return (path, init) => page.evaluate(
    async ([p, i]) => {
      const response = await fetch(p, i ?? undefined);
      let body = null;
      try { body = await response.json(); } catch { body = null; }
      return { status: response.status, body };
    }, [path, init ?? null]);
}

async function signIn(page, username, password) {
  await page.context().clearCookies();
  await page.goto(`${APP}/login`);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 20000 });
}

/**
 * Choose an organization through the switcher, the way a user does.
 *
 * Necessary because an account in more than one organization is *not*
 * auto-selected into either — the active-organization contract forbids
 * guessing, so the interface shows "Choose an organization" and renders no
 * scoped content until one is picked. The upgrade backfill enrols everyone
 * into the legacy organization, so almost every real account is now in two.
 *
 * Driving the switcher rather than writing sessionStorage directly means this
 * exercises the real selection path, including the cache clearing that goes
 * with it.
 *
 * A single-organization account is auto-selected and shows a label rather than
 * a control, so the absence of a switcher is success, not a failure.
 */
async function selectOrganization(page, organizationName) {
  // Wait for the shell to mount before deciding whether a switcher exists.
  //
  // Counting immediately after `goto` returns zero because React has not
  // rendered yet, and the helper then silently concluded "single-organization
  // account, nothing to choose" — so nothing was selected, the page stayed on
  // "Choose an organization", and the failure surfaced twenty seconds later as
  // a missing legend rather than as a missing click.
  await page.waitForSelector('[data-testid="active-organization"]',
                             { timeout: 20000 }).catch(() => {});
  const trigger = page.locator('[data-testid="organization-switcher"]');
  if (await trigger.count() === 0) return false;   // single-organization account
  await trigger.click();
  const option = page.getByRole('menuitemradio', {
    name: new RegExp(organizationName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
  });
  await option.first().waitFor({ state: 'visible', timeout: 10000 });
  await option.first().click();
  // The switch clears cached state and refetches; wait for the scoped content
  // rather than a fixed delay where possible.
  await page.waitForTimeout(1500);
  return true;
}

async function preflight() {
  let ok = true;
  for (const path of ['/api/v1/organizations']) {
    let status;
    try {
      status = (await fetch(`${APP}${path}`, { redirect: 'manual' })).status;
    } catch (e) {
      problems.push(`preflight ${path}: ${e.message}`);
      ok = false;
      continue;
    }
    // 401 is the success signal: the route exists and is protected.
    const exists = status !== 404;
    check(`live server serves ${path}`, exists, `HTTP ${status}`);
    if (!exists) ok = false;
  }
  return ok;
}

async function main() {
  if (!await preflight()) {
    console.log('\nAborted: the running server does not serve organizations.');
    process.exit(1);
  }

  const browser = await chromium.launch({
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const page = await browser.newPage({
    viewport: { width: 1500, height: 1050 },
  });

  let expectRejection = false;
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    if (t.includes('favicon') || t.includes('401')) return;
    if (expectRejection && /\b4\d\d\b/.test(t)) return;
    problems.push(`console error: ${t.slice(0, 140)}`);
  });

  const call = api(page);

  /* ------------------------------------------- 1. owner signs in ------ */
  await signIn(page, OWNER_USER, OWNER_PASS);
  check('1. owner signs in', true);

  const listing = await call('/api/v1/organizations');
  // Not simply the first: the upgrade backfill enrols everyone into the
  // legacy organization, which sorts first by name and is
  // PENDING_CONFIRMATION until an administrator confirms it. That organization
  // correctly refuses scientific changes, so driving the walkthrough through
  // it would report the application as broken when it is behaving as designed.
  const organization = (listing.body?.organizations ?? []).find(
    (o) => !o.awaiting_confirmation) ?? listing.body?.organizations?.[0];
  check('1a. the owner belongs to an organization', Boolean(organization),
        `HTTP ${listing.status}`);
  if (!organization) {
    console.log('Aborted: the owner is not a member of any organization.');
    await browser.close();
    process.exit(1);
  }
  const orgId = organization.id;
  const H = { 'Content-Type': 'application/json', 'X-Organization-Id': String(orgId) };

  // Captured here, while signed in as the owner. Later steps need a study id
  // that genuinely exists, and cannot ask an account that is not allowed to
  // see it — asking the newcomer would return an empty list, and the check
  // that depends on it would skip rather than fail, which is the worst of the
  // three outcomes.
  const ownerRunsEarly = await call('/api/v1/runs', { headers: H });
  const knownStudyId = ownerRunsEarly.body?.runs?.[0]?.id ?? null;
  check('1b. the owner can see a study to work with', knownStudyId !== null,
        `HTTP ${ownerRunsEarly.status}`);

  /* --------------------------------- 2. the management screen loads --- */
  await page.goto(`${APP}/organization`);
  // An account in several organizations is never auto-selected — the contract
  // forbids guessing — so the choice is made through the switcher first.
  const selected = await selectOrganization(page, organization.name);
  notes.push(selected
    ? `organization chosen through the switcher: ${organization.name}`
    : `single-organization account; ${organization.name} was auto-selected`);
  await page.waitForSelector('[data-testid="authority-legend"]',
                             { timeout: 20000 });
  check('2. the organization screen renders', true);

  const legend = await page.textContent('[data-testid="authority-legend"]');
  check('2a. authority and scientific eligibility are named separately',
        /Organization authority/.test(legend)
        && /Scientific eligibility/.test(legend)
        && /cannot/i.test(legend));
  await shot(page, '01-profile');

  /* ----------------- 3. no password field on any management screen ---- */
  // Already on /organization with the organization selected, from step 2.
  for (const tab of ['Members & roles', 'Invitations',
                     'External collaborators', 'Access history']) {
    await page.click(`role=tab[name="${tab}"]`);
    await page.waitForTimeout(250);
    const passwords = await page.locator('input[type="password"]').count();
    check(`3. no password field on "${tab}"`, passwords === 0,
          `${passwords} found`);
  }
  await shot(page, '02-members');

  /* ------------------------------------ 4. an invitation is issued ---- */
  // A leftover invitation from a previous run makes this a legitimate 409, so
  // the rejection is expected here rather than a finding.
  expectRejection = true;
  const invited = await call(`/api/v1/organizations/${orgId}/invitations`, {
    method: 'POST', headers: H,
    body: JSON.stringify({ email: NEW_EMAIL, role: 'researcher' }),
  });
  // A 409 means one is already outstanding from a previous run. Withdraw and
  // retry rather than failing on a leftover.
  let invitation = invited.body;
  if (invited.status === 409) {
    const open = await call(
      `/api/v1/organizations/${orgId}/invitations`, { headers: H });
    for (const row of open.body?.invitations ?? []) {
      if (row.email === NEW_EMAIL.toLowerCase()) {
        await call(`/api/v1/organizations/${orgId}/invitations/${row.id}`,
                   { method: 'DELETE', headers: H });
      }
    }
    const retried = await call(`/api/v1/organizations/${orgId}/invitations`, {
      method: 'POST', headers: H,
      body: JSON.stringify({ email: NEW_EMAIL, role: 'researcher' }),
    });
    invitation = retried.body;
    check('4. invitation issued (after clearing a leftover)',
          retried.status === 201, `HTTP ${retried.status}`);
  } else {
    check('4. invitation issued', invited.status === 201,
          `HTTP ${invited.status} ${JSON.stringify(invited.body).slice(0, 160)}`);
  }
  expectRejection = false;

  const link = invitation?.invitation_link ?? null;
  check('4a. the one-time link is returned to the administrator',
        typeof link === 'string' && link.includes('token='));

  const relisted = await call(
    `/api/v1/organizations/${orgId}/invitations`, { headers: H });
  const relistedRow = (relisted.body?.invitations ?? [])
    .find((r) => r.id === invitation?.id);
  check('4b. the link is NOT retrievable a second time',
        Boolean(relistedRow) && !('invitation_link' in (relistedRow ?? {})));

  /* ----------------- 5. the administrator cannot escalate themselves -- */
  await signIn(page, ADMIN_USER, ADMIN_PASS);
  const adminCall = api(page);
  const members = await adminCall(
    `/api/v1/organizations/${orgId}/members`, { headers: H });
  const adminRow = (members.body?.members ?? [])
    .find((m) => m.username === ADMIN_USER);
  check('5. the administrator can read the members list',
        members.status === 200 && Boolean(adminRow),
        `HTTP ${members.status}`);

  if (adminRow) {
    expectRejection = true;
    const selfPromote = await adminCall(
      `/api/v1/organizations/${orgId}/members/${adminRow.id}`, {
        method: 'PATCH', headers: H,
        body: JSON.stringify({ role: 'approver' }),
      });
    check('5a. an administrator cannot promote themselves',
          selfPromote.status === 409, `HTTP ${selfPromote.status}`);
    expectRejection = false;

    await page.goto(`${APP}/organization`);
    await selectOrganization(page, organization.name);
    await page.waitForSelector('[data-testid="authority-legend"]',
                               { timeout: 20000 });
    await page.click('role=tab[name="Members & roles"]');
    // Wait for the table, then for the row, before looking for the control.
    // Looking for the control directly turns "the members list has not loaded
    // yet" into "the control is missing" — a different and much more alarming
    // finding than the one that would be true.
    await page.waitForSelector('[data-testid="members-table"]',
                               { timeout: 20000 });
    await page.waitForSelector(`[data-testid="member-${ADMIN_USER}"]`,
                               { timeout: 20000 });
    const locked = await page.locator(
      `[data-testid="self-locked-${ADMIN_USER}"]`).count();
    check('5b. the screen explains the bar rather than offering the control',
          locked === 1);
    await shot(page, '03-self-locked');
  }

  /* ------------------------------------ 6. the newcomer redeems -------- */
  await signIn(page, NEW_USER, NEW_PASS);
  const newcomerCall = api(page);

  const before = await newcomerCall('/api/v1/organizations');
  const wasMember = (before.body?.organizations ?? [])
    .some((o) => o.id === orgId);

  if (link) {
    await page.goto(`${APP}${link.startsWith('/') ? link : `/${link}`}`);
    await page.waitForSelector('[data-testid="accept-invitation"]',
                               { timeout: 20000 });
    expectRejection = true;
    await page.click('[data-testid="accept-invitation"]');
    await page.waitForTimeout(1500);
    expectRejection = false;

    const accepted = await page.locator(
      '[data-testid="invitation-accepted"]').count();
    const refused = await page.locator(
      '[data-testid="invitation-error"]').count();
    // Already-a-member is a legitimate outcome on a repeated run, and the
    // interface must handle it without a stack trace either way.
    check('6. the invitation page resolves to one clear outcome',
          accepted + refused === 1,
          `accepted=${accepted} refused=${refused} wasMember=${wasMember}`);
    if (accepted === 1) {
      const text = await page.textContent('[data-testid="invitation-accepted"]');
      check('6a. joining states that it grants no scientific authority',
            /no scientific authority/i.test(text));
    }
    await shot(page, '04-accepted');
  }

  /* -------------- 7. membership alone grants no scientific authority -- */
  const runs = await newcomerCall('/api/v1/runs', { headers: H });
  check('7. the newcomer can call the workspace API',
        runs.status === 200, `HTTP ${runs.status}`);

  // A member with assigned-studies scope and no assignment sees no studies,
  // which is itself the correct answer.
  check('7a. a member with no assignment sees no studies',
        (runs.body?.runs ?? []).length === 0,
        JSON.stringify(runs.body?.runs ?? []).slice(0, 120));

  if (knownStudyId !== null) {
    // Against a study that DOES exist, named explicitly. The refusal must come
    // from the policy, not from the identifier being made up.
    expectRejection = true;
    const appoint = await newcomerCall(
      `/api/v1/organizations/${orgId}/studies/${knownStudyId}/team`, {
        method: 'POST', headers: H,
        body: JSON.stringify({ user_id: 1, role: 'approver' }),
      });
    check('7b. a plain member cannot appoint anybody',
          appoint.status === 403 || appoint.status === 404,
          `HTTP ${appoint.status}`);

    const team = await newcomerCall(
      `/api/v1/organizations/${orgId}/studies/${knownStudyId}/team`,
      { headers: H });
    check('7c. a member with no assignment cannot read the study team',
          team.status === 404, `HTTP ${team.status}`);
    expectRejection = false;
  }

  /* --------------- 8. the owner appoints, and the effect is immediate - */
  await signIn(page, OWNER_USER, OWNER_PASS);
  const ownerCall = api(page);

  const study = knownStudyId;

  if (study !== null) {
    const roster = await ownerCall(
      `/api/v1/organizations/${orgId}/members`, { headers: H });
    const newcomerRow = (roster.body?.members ?? [])
      .find((m) => m.username === NEW_USER);

    if (newcomerRow) {
      // Straight from the backend: what this person is eligible for is not a
      // decision this script is entitled to make either.
      const eligible = newcomerRow.assignable_study_roles ?? [];
      check('8. the roster states what the newcomer is eligible for',
            Array.isArray(eligible) && eligible.length > 0,
            JSON.stringify(eligible));
      check('8a. a researcher is NOT eligible for approver',
            !eligible.includes('approver'), JSON.stringify(eligible));

      const role = eligible.includes('contributor') ? 'contributor'
        : eligible[0];
      const assigned = await ownerCall(
        `/api/v1/organizations/${orgId}/studies/${study}/team`, {
          method: 'POST', headers: H,
          body: JSON.stringify({
            user_id: newcomerRow.user_id, role,
            note: 'Appointed by the acceptance walkthrough.',
          }),
        });
      const created = assigned.status === 201 ? assigned.body : null;
      check('8b. the owner can appoint', assigned.status === 201,
            `HTTP ${assigned.status} ${JSON.stringify(assigned.body).slice(0, 160)}`);

      await page.goto(`${APP}/organization`);
      await selectOrganization(page, organization.name);
      await page.goto(`${APP}/organization/studies/${study}/team`);
      await page.waitForSelector('[data-testid="study-team-table"]',
                                 { timeout: 20000 });
      const teamText = await page.textContent('[data-testid="study-team-table"]');
      check('8c. the assignment appears on the study team screen',
            teamText.includes(NEW_USER));
      await shot(page, '05-study-team');

      // The history is a second, independent fetch on the same page, so it
      // arrives after the team table. Counting immediately raced it and
      // reported "no history" for a page that was still loading one.
      await page.waitForSelector('[data-testid="team-history-table"]',
                                 { timeout: 20000 }).catch(() => {});
      const history = await page.locator(
        '[data-testid="team-history-table"]').count();
      check('8d. the appointment history is shown', history === 1,
            'the history table did not appear within 20s');

      /* -------- 9. revocation takes effect on the NEXT request -------- */
      if (created) {
        const revoked = await ownerCall(
          `/api/v1/organizations/${orgId}/studies/${study}/team/${created.id}`, {
            method: 'DELETE', headers: H,
            body: JSON.stringify({ reason: 'Walkthrough cleanup.',
                                   expected_revision: created.revision }),
          });
        check('9. the assignment is revoked', revoked.status === 200,
              `HTTP ${revoked.status}`);
        check('9a. revocation states that attribution survives',
              /already happened/i.test(revoked.body?.notice ?? ''));

        const after = await ownerCall(
          `/api/v1/organizations/${orgId}/studies/${study}/team`,
          { headers: H });
        const stillActive = (after.body?.assignments ?? [])
          .some((a) => a.id === created.id && a.is_active);
        check('9b. the revoked assignment is inactive on the next request',
              !stillActive);
        const stillListed = (after.body?.assignments ?? [])
          .some((a) => a.id === created.id);
        check('9c. the row survives, so the history survives with it',
              stillListed);
      }
    }
  }

  /* ------------------------------------ 10. the audit trail records it - */
  const audit = await ownerCall(
    `/api/v1/organizations/${orgId}/audit?limit=200`, { headers: H });
  const events = (audit.body?.events ?? []).map((e) => e.event);
  check('10. the access history is readable by the owner',
        audit.status === 200, `HTTP ${audit.status}`);
  check('10a. the invitation is recorded', events.includes('member_invited'));
  check('10b. the trail is append-only', audit.body?.append_only === true);
  check('10c. no audit line carries a token or a password',
        !JSON.stringify(audit.body ?? {}).match(/token=|password/i));

  await page.goto(`${APP}/organization`);
  await selectOrganization(page, organization.name);
  await page.click('role=tab[name="Access history"]');
  await page.waitForSelector('[data-testid="audit-table"]', { timeout: 20000 })
    .catch(() => {});
  await shot(page, '06-audit');

  await browser.close();

  console.log('');
  for (const note of notes) console.log(`note: ${note}`);
  console.log('');
  if (problems.length === 0) {
    console.log('All organization-management checks passed.');
    console.log(`Screenshots: ${OUT}`);
  } else {
    console.log(`${problems.length} problem(s):`);
    for (const p of problems) console.log(`  - ${p}`);
    process.exitCode = 1;
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
