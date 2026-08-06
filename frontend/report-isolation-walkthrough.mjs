/**
 * Live cross-organization walkthrough of the medical-report pathway.
 *
 * What this proves that no other suite can
 * ----------------------------------------
 * The pytest isolation suite drives the API directly, and would pass against a
 * frontend that never calls it. The vitest suite stubs `fetch`, and would pass
 * against a backend that does not serve these routes at all. Only this script
 * uploads a real document through a real browser session, then tries to reach
 * it from a *different organization's* account against the same running server.
 *
 * The claim under test is confidentiality, not access control in the abstract:
 * a patient's document, its name, its size, its hash, its clinical text and
 * even the fact that it exists must all be unobservable to somebody in another
 * organization — and equally to an administrator inside the same one.
 *
 * A marker string is written into the uploaded document. Every negative check
 * searches the raw response body for it rather than for a particular field, so
 * a leak through a route nobody thought to name still fails the run.
 *
 * Three accounts, and they matter
 * -------------------------------
 * An author in organization A, an author in organization B, and an
 * administrator in A. Two would prove cross-organization isolation only; the
 * administrator is what proves the *other* separation — that managing access
 * does not confer the right to read patient documents.
 *
 * Credentials come from the environment. Nothing is embedded.
 */

import { chromium } from 'playwright';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const OUT = resolve('../docs/screenshots');
mkdirSync(OUT, { recursive: true });

// The author in the first organization.
const { user: A_USER, pass: A_PASS } = walkthroughCredentials();
const B_USER = process.env.NANOBIO_REPORT_OTHER_USER;
const B_PASS = process.env.NANOBIO_REPORT_OTHER_PASSWORD;
const ADMIN_USER = process.env.NANOBIO_REPORT_ADMIN_USER;
const ADMIN_PASS = process.env.NANOBIO_REPORT_ADMIN_PASSWORD;

if (!B_USER || !B_PASS || !ADMIN_USER || !ADMIN_PASS) {
  console.error(`
The medical-report walkthrough needs THREE accounts in TWO organizations:

  - the author, from NANOBIO_WALKTHROUGH_USER / _PASSWORD
  - an author in a DIFFERENT organization
  - an administrator in the FIRST organization

  PowerShell:
    $env:NANOBIO_REPORT_OTHER_USER      = 'walkthrough_other_org'
    $env:NANOBIO_REPORT_OTHER_PASSWORD  = '<their password>'
    $env:NANOBIO_REPORT_ADMIN_USER      = 'walkthrough_org_admin'
    $env:NANOBIO_REPORT_ADMIN_PASSWORD  = '<their password>'

Two accounts would prove cross-organization isolation only. The administrator
is what proves that managing access does not confer the right to read a
patient's document.

Nothing was run and no browser was launched.
`);
  process.exit(2);
}

/** Written into the uploaded document. Searched for in every refusal. */
const MARKER = `WALKTHROUGHPATIENT${Date.now().toString(36).toUpperCase()}`;

const problems = [];
const log = (l, v) => console.log(`${l.padEnd(64, '.')} ${v}`);
function check(label, ok, detail = '') {
  log(label, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
}

async function shot(page, name) {
  await page.screenshot({ path: resolve(OUT, `report-isolation-${name}.png`),
                          fullPage: true });
}

function api(page) {
  return (path, init) => page.evaluate(
    async ([p, i]) => {
      const response = await fetch(p, i ?? undefined);
      let body = null;
      let text = '';
      try { text = await response.text(); } catch { text = ''; }
      try { body = JSON.parse(text); } catch { body = null; }
      return { status: response.status, body, text };
    }, [path, init ?? null]);
}

/** Upload a document through the real multipart path, in the browser. */
function uploadDocument(page) {
  return (marker, organizationId) => page.evaluate(
    async ([m, orgId]) => {
      const content =
        'SYNTHETIC DEMONSTRATION DOCUMENT -- NOT A REAL MEDICAL REPORT\n'
        + 'This document is fictional and invented for software testing.\n'
        + 'Diagnosis: invasive ductal carcinoma of the left breast.\n'
        + `Case reference: ${m}\n`;
      const form = new FormData();
      form.append('file', new Blob([content], { type: 'text/plain' }),
                  `${m.toLowerCase()}.txt`);
      form.append('classification', 'synthetic');
      form.append('attested', 'true');
      const headers = orgId ? { 'X-Organization-Id': String(orgId) } : {};
      const response = await fetch('/api/v1/reports',
                                   { method: 'POST', body: form, headers });
      let body = null;
      try { body = await response.json(); } catch { body = null; }
      return { status: response.status, body };
    }, [marker, organizationId ?? null]);
}

async function signIn(page, username, password) {
  await page.context().clearCookies();
  await page.goto(`${APP}/login`);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 20000 });
}

async function preflight() {
  let ok = true;
  for (const path of ['/api/v1/reports']) {
    let status;
    try {
      status = (await fetch(`${APP}${path}`, { redirect: 'manual' })).status;
    } catch (e) {
      problems.push(`preflight ${path}: ${e.message}`);
      ok = false;
      continue;
    }
    const exists = status !== 404;
    check(`live server serves ${path}`, exists, `HTTP ${status}`);
    if (!exists) ok = false;
  }
  return ok;
}

async function main() {
  if (!await preflight()) {
    console.log('\nAborted: the running server does not serve reports.');
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

  /* --------------------------- 1. the author uploads ------------------ */
  await signIn(page, A_USER, A_PASS);
  const authorCall = api(page);
  const upload = uploadDocument(page);

  const orgs = await authorCall('/api/v1/organizations');
  const memberships = orgs.body?.organizations ?? [];
  check('1. the author belongs to an organization', memberships.length > 0,
        `HTTP ${orgs.status}`);

  // Not simply `organizations[0]`.
  //
  // An account can belong to several — the upgrade backfill enrols everyone
  // into the legacy organization, which sorts first by name and is
  // PENDING_CONFIRMATION until an administrator confirms it. That organization
  // correctly refuses scientific and report writes, so uploading into it fails
  // and the script would report the *application* as broken when it was
  // behaving exactly as designed.
  //
  // Choosing a confirmed organization is also what a real multi-organization
  // user does, which is the case this whole milestone exists to support.
  const organization = memberships.find((o) => !o.awaiting_confirmation)
    ?? memberships[0];
  check('1a. a confirmed organization is available',
        Boolean(organization) && !organization.awaiting_confirmation,
        `${memberships.length} membership(s), all awaiting confirmation`);
  if (!organization) {
    console.log('Aborted: the author is not a member of any organization.');
    await browser.close();
    process.exit(1);
  }
  const orgId = organization.id;

  const created = await upload(MARKER, orgId);
  check('2. the author uploads a document', created.status === 201,
        `HTTP ${created.status} ${JSON.stringify(created.body).slice(0, 160)}`);
  const assessmentId = created.body?.assessment_id;
  const displayName = created.body?.display_name;
  const contentHash = created.body?.content_hash;
  if (!assessmentId) {
    console.log('Aborted: nothing was uploaded, so nothing can be tested.');
    await browser.close();
    process.exit(1);
  }

  /* ------------------------ 3. the author can read it back ------------ */
  const H = { 'X-Organization-Id': String(orgId) };
  const own = await authorCall(`/api/v1/reports/${assessmentId}`,
                               { headers: H });
  check('3. the author reads their own assessment', own.status === 200,
        `HTTP ${own.status}`);
  check('3a. the document is genuinely populated', own.text.includes(MARKER));

  const download = await authorCall(
    `/api/v1/reports/${assessmentId}/document`, { headers: H });
  check('3b. the author downloads the original document',
        download.status === 200, `HTTP ${download.status}`);

  await page.goto(`${APP}/patient-assessments`);
  await page.waitForTimeout(2000);
  await shot(page, '01-author-view');

  /* --------------- 4. the other organization sees nothing ------------- */
  await signIn(page, B_USER, B_PASS);
  const otherCall = api(page);
  expectRejection = true;

  const otherOrgs = await otherCall('/api/v1/organizations');
  const otherOrgId = otherOrgs.body?.organizations?.[0]?.id ?? null;
  check('4. the second account is in a DIFFERENT organization',
        otherOrgId !== null && otherOrgId !== orgId,
        `theirs=${otherOrgId} authors=${orgId}`);

  for (const [label, path] of [
    ['detail', `/api/v1/reports/${assessmentId}`],
    ['document', `/api/v1/reports/${assessmentId}/document`],
    ['history', `/api/v1/reports/${assessmentId}/history`],
  ]) {
    const response = await otherCall(path);
    check(`4a. foreign ${label} is 404`, response.status === 404,
          `HTTP ${response.status}`);
    check(`4b. foreign ${label} leaks no patient marker`,
          !response.text.includes(MARKER));
    check(`4c. foreign ${label} leaks no document name or hash`,
          !response.text.includes(displayName ?? ' ')
          && !response.text.includes(contentHash ?? ' '));
  }

  // Indistinguishable from an identifier that never existed.
  const foreign = await otherCall(`/api/v1/reports/${assessmentId}`);
  const absent = await otherCall('/api/v1/reports/99999999');
  check('4d. a foreign and an absent identifier answer identically',
        foreign.status === absent.status && foreign.text === absent.text,
        `${foreign.status}/${absent.status}`);

  const otherList = await otherCall('/api/v1/reports');
  check('4e. the foreign listing omits it entirely',
        otherList.status === 200 && !otherList.text.includes(MARKER),
        `HTTP ${otherList.status}`);

  const search = await otherCall(
    `/api/v1/reports?search=${encodeURIComponent(displayName ?? '')}`);
  check('4f. searching for its name from another organization finds nothing',
        search.status === 200
        && (search.body?.assessments ?? []).length === 0
        && !search.text.includes(MARKER),
        `HTTP ${search.status}`);

  expectRejection = false;
  await page.goto(`${APP}/patient-assessments`);
  await page.waitForTimeout(2000);
  const otherScreen = await page.textContent('body');
  check('4g. the other organization\'s screen shows no trace of it',
        !otherScreen.includes(MARKER) && !otherScreen.includes(displayName));
  await shot(page, '02-other-organization');

  /* ----------- 5. the administrator manages access, not evidence ------ */
  await signIn(page, ADMIN_USER, ADMIN_PASS);
  const adminCall = api(page);
  expectRejection = true;

  const adminDetail = await adminCall(`/api/v1/reports/${assessmentId}`,
                                      { headers: H });
  check('5. an administrator in the SAME organization is refused the record',
        adminDetail.status === 403, `HTTP ${adminDetail.status}`);
  check('5a. and the refusal carries no patient content',
        !adminDetail.text.includes(MARKER));

  const adminDownload = await adminCall(
    `/api/v1/reports/${assessmentId}/document`, { headers: H });
  check('5b. an administrator cannot download the document',
        adminDownload.status === 403, `HTTP ${adminDownload.status}`);

  const adminHistory = await adminCall(
    `/api/v1/reports/${assessmentId}/history`, { headers: H });
  check('5c. an administrator CAN read the access trail',
        adminHistory.status === 200, `HTTP ${adminHistory.status}`);
  check('5d. the trail names the events and not the content',
        adminHistory.status === 200
        && (adminHistory.body?.events ?? []).length > 0
        && !adminHistory.text.includes(MARKER)
        && !adminHistory.text.includes(displayName ?? ' '));

  const adminUpload = await upload('ADMINSHOULDNOTUPLOAD', orgId);
  check('5e. an administrator cannot upload a patient document',
        adminUpload.status === 403, `HTTP ${adminUpload.status}`);

  expectRejection = false;
  await shot(page, '03-administrator');

  /* ------------------------------- 6. cleanup ------------------------- */
  await signIn(page, A_USER, A_PASS);
  const cleanup = api(page);
  const deleted = await cleanup(`/api/v1/reports/${assessmentId}`,
                                { method: 'DELETE', headers: H });
  check('6. the author deletes their own assessment', deleted.status === 200,
        `HTTP ${deleted.status}`);

  // The 404 below is the expected outcome, so it is not a finding.
  expectRejection = true;
  const afterDelete = await cleanup(`/api/v1/reports/${assessmentId}`,
                                    { headers: H });
  check('6a. it is gone', afterDelete.status === 404,
        `HTTP ${afterDelete.status}`);
  expectRejection = false;

  await browser.close();

  console.log('');
  if (problems.length === 0) {
    console.log('All medical-report isolation checks passed.');
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
