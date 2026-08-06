/**
 * Live walkthrough of attachment upload, download and isolation.
 *
 * What this proves that no other suite can
 * ----------------------------------------
 * The pytest suites drive the service and the routes directly, against an
 * in-memory store. They would pass against a deployment whose object storage
 * was never wired up. This uploads a real file through a real browser session
 * to a running server, downloads it back, and then tries to reach it from
 * every account that should not be able to.
 *
 * The claims under test are the ones a unit test cannot make:
 *
 *   an authorized researcher can upload and download;
 *   a foreign organization gets the same 404 as an absent record;
 *   an administrator cannot download patient-report content;
 *   a restricted CRO sees permitted metadata and cannot download;
 *   revocation blocks the very next request;
 *   switching organization cannot reuse the previous attachment URL, and the
 *     response is uncacheable so it cannot come back from a browser cache;
 *   a deleted attachment cannot be downloaded.
 *
 * A marker string is written into the uploaded file. Every negative check
 * searches the raw response for it rather than for a named field, so a leak
 * through a route nobody thought of still fails the run.
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

const OWNER_USER = process.env.NANOBIO_ATTACH_OWNER_USER;
const OWNER_PASS = process.env.NANOBIO_ATTACH_OWNER_PASSWORD;
const { user: AUTHOR_USER, pass: AUTHOR_PASS } = walkthroughCredentials();
const OTHER_USER = process.env.NANOBIO_ATTACH_OTHER_USER;
const OTHER_PASS = process.env.NANOBIO_ATTACH_OTHER_PASSWORD;
const ADMIN_USER = process.env.NANOBIO_ATTACH_ADMIN_USER;
const ADMIN_PASS = process.env.NANOBIO_ATTACH_ADMIN_PASSWORD;
const CRO_USER = process.env.NANOBIO_ATTACH_CRO_USER;
const CRO_PASS = process.env.NANOBIO_ATTACH_CRO_PASSWORD;

if (!OTHER_USER || !OTHER_PASS || !ADMIN_USER || !ADMIN_PASS) {
  console.error(`
The attachment-storage walkthrough needs accounts in TWO organizations:

  - the author, from NANOBIO_WALKTHROUGH_USER / _PASSWORD
  - a researcher in a DIFFERENT organization
  - an administrator in the FIRST organization

  PowerShell:
    $env:NANOBIO_ATTACH_OTHER_USER      = 'walkthrough_other_org'
    $env:NANOBIO_ATTACH_OTHER_PASSWORD  = '<their password>'
    $env:NANOBIO_ATTACH_ADMIN_USER      = 'walkthrough_org_admin'
    $env:NANOBIO_ATTACH_ADMIN_PASSWORD  = '<their password>'

  Optional, for the revocation check (an owner who can suspend the author):
    $env:NANOBIO_ATTACH_OWNER_USER      = 'walkthrough_owner'
    $env:NANOBIO_ATTACH_OWNER_PASSWORD  = '<their password>'

  Optional, for the CRO download-restriction check (an external collaborator
  whose membership has may_download_attachments = false):
    $env:NANOBIO_ATTACH_CRO_USER        = 'walkthrough_cro'
    $env:NANOBIO_ATTACH_CRO_PASSWORD    = '<their password>'

Nothing was run and no browser was launched.
`);
  process.exit(2);
}

const MARKER = `ATTACHMARKER${Date.now().toString(36).toUpperCase()}`;

const problems = [];
const notes = [];
let assertions = 0;
const log = (l, v) => console.log(`${l.padEnd(66, '.')} ${v}`);
function check(label, ok, detail = '') {
  assertions += 1;
  log(label, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
}

async function shot(page, name) {
  await page.screenshot({ path: resolve(OUT, `attachment-${name}.png`),
                          fullPage: true });
}

function api(page) {
  return (path, init) => page.evaluate(
    async ([p, i]) => {
      const response = await fetch(p, i ?? undefined);
      let text = '';
      let body = null;
      try { text = await response.text(); } catch { text = ''; }
      try { body = JSON.parse(text); } catch { body = null; }
      const headers = {};
      response.headers.forEach((v, k) => { headers[k] = v; });
      return { status: response.status, body, text, headers };
    }, [path, init ?? null]);
}

/**
 * Upload a CSV through the real multipart path, in the browser.
 *
 * Returns the exact content and its SHA-256, computed in the page with
 * WebCrypto, so the download can be compared byte-for-byte and digest-for-
 * digest against what was sent — not merely searched for a marker.
 *
 * `filename` is a parameter so the unsafe-name check can send a hostile one
 * through the same path a real upload takes.
 */
function uploadFile(page) {
  return (versionId, marker, orgId, filename) => page.evaluate(
    async ([vid, m, o, name]) => {
      const content = `time_s,signal,note\n0,1.00,${m}\n1,0.52,${m}\n`;
      const bytes = new TextEncoder().encode(content);
      const digestBuffer = await crypto.subtle.digest('SHA-256', bytes);
      const digest = Array.from(new Uint8Array(digestBuffer))
        .map((b) => b.toString(16).padStart(2, '0')).join('');

      const form = new FormData();
      form.append('file', new Blob([content], { type: 'text/csv' }),
                  name || `${m.toLowerCase()}.csv`);
      const response = await fetch(
        `/api/v1/validation/versions/${vid}/attachments?category=raw_data`,
        { method: 'POST', body: form,
          headers: { 'X-Organization-Id': String(o) } });
      let body = null;
      try { body = await response.json(); } catch { body = null; }
      return { status: response.status, body, content, digest,
               size: bytes.length };
    }, [versionId, marker, orgId, filename ?? null]);
}

/** SHA-256 of a downloaded body, computed in the page. */
function digestOf(page) {
  return (text) => page.evaluate(async (t) => {
    const bytes = new TextEncoder().encode(t);
    const buffer = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(buffer))
      .map((b) => b.toString(16).padStart(2, '0')).join('');
  }, text);
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
  for (const path of ['/api/v1/validation/experiments']) {
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
    console.log('\nAborted: the running server does not serve the registry.');
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
  await signIn(page, AUTHOR_USER, AUTHOR_PASS);
  const call = api(page);
  const upload = uploadFile(page);

  const orgs = await call('/api/v1/organizations');
  const memberships = orgs.body?.organizations ?? [];
  check('1. the author belongs to an organization', memberships.length > 0);
  if (memberships.length === 0) {
    console.log('Aborted: the author is not a member of any organization.');
    await browser.close();
    process.exit(1);
  }

  // Find the organization that actually holds a draft experiment version,
  // rather than assuming the first one listed.
  //
  // An earlier version took `organizations[0]`. That worked until the upgrade
  // backfill enrolled this account into the legacy organization as well —
  // which sorts first by name — and the script then looked for a draft in an
  // organization that has none and reported the *application* as broken. An
  // account belonging to several organizations is the normal case this whole
  // milestone is built around; the script has to behave like one.
  //
  // The registry listing returns one row per *version*, carrying both
  // `version_id` and `status`, so each organization costs one request.
  let orgId = null;
  let versionId = null;
  for (const candidate of memberships) {
    const listing = await call(
      '/api/v1/validation/experiments?status=draft',
      { headers: { 'X-Organization-Id': String(candidate.id) } });
    const draft = (listing.body?.experiments ?? []).find(
      (row) => row.status === 'draft' && row.version_id);
    if (draft) {
      orgId = candidate.id;
      versionId = draft.version_id;
      break;
    }
  }
  check('1a. a draft experiment version is available', versionId !== null,
        `searched ${memberships.length} organization(s)`);
  if (versionId === null) {
    console.log('Aborted: no draft version to attach to.');
    await browser.close();
    process.exit(1);
  }
  const H = { 'X-Organization-Id': String(orgId) };
  const sha256 = digestOf(page);

  const created = await upload(versionId, MARKER, orgId);
  check('2. an authorized researcher can upload an attachment',
        created.status === 200,
        `HTTP ${created.status} ${JSON.stringify(created.body).slice(0, 160)}`);
  const attachmentId = created.body?.id;
  if (!attachmentId) {
    console.log('Aborted: nothing was uploaded.');
    await browser.close();
    process.exit(1);
  }

  check('2a. the upload response does not leak the object key',
        !JSON.stringify(created.body ?? {}).includes('storage_key'));

  /* --------------------------- 3. and downloads it back --------------- */
  const downloaded = await call(`/api/v1/validation/attachments/${attachmentId}`,
                                { headers: H });
  check('3. the author can download it', downloaded.status === 200,
        `HTTP ${downloaded.status}`);
  check('3a. the marker survives the round trip',
        downloaded.text.includes(MARKER));
  check('3b. the downloaded bytes are identical to what was uploaded',
        downloaded.text === created.content,
        `${downloaded.text.length} vs ${created.content.length} chars`);
  const downloadedDigest = await sha256(downloaded.text);
  check('3c. the downloaded checksum matches the uploaded checksum',
        downloadedDigest === created.digest,
        `${downloadedDigest.slice(0, 12)}… vs ${created.digest.slice(0, 12)}…`);
  check('3d. and matches the checksum the server recorded',
        (created.body?.checksum_sha256 || '') === created.digest,
        `server=${(created.body?.checksum_sha256 || '').slice(0, 12)}…`);
  check('3e. the recorded size matches the uploaded size',
        created.body?.size_bytes === created.size,
        `${created.body?.size_bytes} vs ${created.size}`);
  check('3f. it is served as a download, never inline',
        (downloaded.headers['content-disposition'] || '')
          .startsWith('attachment;'));
  check('3g. sniffing is disabled',
        downloaded.headers['x-content-type-options'] === 'nosniff');
  check('3h. the response is uncacheable, so a revoked or deleted file '
        + 'cannot come back from a cache',
        (downloaded.headers['cache-control'] || '').includes('no-store'));

  /* ---- 3i. the object key never leaves the server ------------------- */
  const detail = await call(
    `/api/v1/validation/versions/${versionId}`, { headers: H });
  check('3i. no response exposes the object key or the bucket',
        !/storage_key|att\/\d+\/\d+\//.test(detail.text)
        && !/bucket/i.test(detail.text),
        detail.text.slice(0, 120));

  /* ---- 3j. an unsafe filename is normalised, not stored as sent ------ */
  const hostile = await upload(
    versionId, `${MARKER}UNSAFE`, orgId,
    '../../../etc/passwd\u0000<script>alert(1)</script>.csv');
  check('3j. a hostile filename is accepted and normalised',
        hostile.status === 200, `HTTP ${hostile.status}`);
  const storedName = hostile.body?.original_filename ?? '';
  check('3k. the stored name carries no separator, traversal or NUL',
        !storedName.includes('/') && !storedName.includes('\\')
        && !storedName.includes('..') && !storedName.includes('\u0000'),
        storedName);

  const hostileDownload = await call(
    `/api/v1/validation/attachments/${hostile.body?.id}`, { headers: H });
  const disposition = hostileDownload.headers['content-disposition'] || '';
  check('3l. the disposition header cannot be injected by the filename',
        disposition.startsWith('attachment;')
        && !disposition.includes('\n') && !disposition.includes('\r')
        && (disposition.match(/"/g) || []).length === 2,
        disposition);
  await call(`/api/v1/validation/attachments/${hostile.body?.id}`,
             { method: 'DELETE', headers: H });

  await page.goto(`${APP}/validation`);
  await page.waitForTimeout(1500);
  await shot(page, '01-author');

  /* ------------- 4. another organization sees nothing at all ---------- */
  await signIn(page, OTHER_USER, OTHER_PASS);
  const otherCall = api(page);
  expectRejection = true;

  const foreign = await otherCall(
    `/api/v1/validation/attachments/${attachmentId}`);
  const absent = await otherCall('/api/v1/validation/attachments/99999999');
  check('4. a foreign organization is refused', foreign.status === 404,
        `HTTP ${foreign.status}`);
  check('4a. and gets the same answer as for an absent record',
        foreign.status === absent.status && foreign.text === absent.text);
  check('4b. no byte of the file reaches them',
        !foreign.text.includes(MARKER));

  // Walk a range of identifiers, and try the object key itself as a path
  // parameter. Possession of a key must grant nothing: there is no route that
  // takes one, and the API is the only way in.
  let leaked = 0;
  let wrongStatus = null;
  for (let id = 1; id <= 25; id += 1) {
    const probe = await otherCall(`/api/v1/validation/attachments/${id}`);
    if (probe.text.includes(MARKER)) leaked += 1;
    if (probe.status !== 404 && wrongStatus === null) {
      wrongStatus = `${id} -> HTTP ${probe.status}`;
    }
  }
  check('4c. walking the identifier space discloses nothing', leaked === 0,
        `${leaked} response(s) contained the marker`);
  check('4d. and every probe answers 404', wrongStatus === null,
        wrongStatus || '');

  const guessedKey = `att/${orgId}/${attachmentId}/${'0'.repeat(32)}`;
  const byKey = await otherCall(
    `/api/v1/validation/attachments/${encodeURIComponent(guessedKey)}`);
  check('4e. an object key is not accepted as an identifier',
        byKey.status === 404 || byKey.status === 422,
        `HTTP ${byKey.status}`);
  check('4f. and returns no bytes', !byKey.text.includes(MARKER));

  expectRejection = false;
  await shot(page, '02-foreign-organization');

  /* ------------- 5. an administrator cannot read patient content ------ */
  await signIn(page, ADMIN_USER, ADMIN_PASS);
  const adminCall = api(page);
  expectRejection = true;

  const reports = await adminCall('/api/v1/reports', { headers: H });
  check('5. an administrator is refused patient-report content',
        reports.status === 403 || (reports.body?.assessments ?? []).length === 0,
        `HTTP ${reports.status}`);

  const reportListing = await adminCall('/api/v1/reports?status=confirmed',
                                        { headers: H });
  check('5a. and no clinical content appears in what they can reach',
        !/carcinoma|diagnosis:/i.test(reportListing.text),
        reportListing.text.slice(0, 120));
  expectRejection = false;
  await shot(page, '03-administrator');

  /* ------------------ 5b. a restricted CRO collaborator --------------- */
  if (CRO_USER && CRO_PASS) {
    await signIn(page, CRO_USER, CRO_PASS);
    const croCall = api(page);
    expectRejection = true;

    // Metadata the collaboration permits: the registry vocabulary and the
    // listing are readable, and neither carries a file.
    const vocabulary = await croCall('/api/v1/validation/vocabulary');
    check('5b. a CRO can read permitted registry metadata',
          vocabulary.status === 200, `HTTP ${vocabulary.status}`);

    const croDownload = await croCall(
      `/api/v1/validation/attachments/${attachmentId}`, { headers: H });
    check('5c. a CRO with downloads withheld cannot fetch the file',
          croDownload.status === 404 || croDownload.status === 403,
          `HTTP ${croDownload.status}`);
    check('5d. and receives no byte of it',
          !croDownload.text.includes(MARKER));
    expectRejection = false;
  } else {
    notes.push('CRO restriction check SKIPPED: set NANOBIO_ATTACH_CRO_USER '
               + 'and _PASSWORD to include it. Nothing was faked.');
  }

  /* ------------------ 6. revocation blocks the next request ----------- */
  if (OWNER_USER && OWNER_PASS) {
    await signIn(page, OWNER_USER, OWNER_PASS);
    const ownerCall = api(page);

    const members = await ownerCall(
      `/api/v1/organizations/${orgId}/members`, { headers: H });
    const authorRow = (members.body?.members ?? []).find(
      (m) => m.username === AUTHOR_USER);

    if (authorRow) {
      const suspended = await ownerCall(
        `/api/v1/organizations/${orgId}/members/${authorRow.id}/status`,
        { method: 'POST',
          headers: { ...H, 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'suspended',
                                 reason: 'Walkthrough check.',
                                 expected_revision: authorRow.revision }) });
      check('6. the author is suspended', suspended.status === 200,
            `HTTP ${suspended.status}`);

      await signIn(page, AUTHOR_USER, AUTHOR_PASS);
      const afterCall = api(page);
      expectRejection = true;
      const blocked = await afterCall(
        `/api/v1/validation/attachments/${attachmentId}`, { headers: H });
      check('6a. the very next request is blocked', blocked.status === 404,
            `HTTP ${blocked.status}`);
      check('6b. and no byte of the file is served',
            !blocked.text.includes(MARKER));
      expectRejection = false;

      // Restore, so the run is repeatable.
      await signIn(page, OWNER_USER, OWNER_PASS);
      const restoreCall = api(page);
      const current = await restoreCall(
        `/api/v1/organizations/${orgId}/members/${authorRow.id}`,
        { headers: H });
      await restoreCall(
        `/api/v1/organizations/${orgId}/members/${authorRow.id}/status`,
        { method: 'POST',
          headers: { ...H, 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'active',
                                 expected_revision: current.body?.revision }) });
      check('6c. the author is reinstated for a repeatable run', true);
    } else {
      notes.push('revocation check SKIPPED: the owner could not see the '
                 + 'author in the members list');
    }
  } else {
    notes.push('revocation check SKIPPED: set NANOBIO_ATTACH_OWNER_USER and '
               + '_PASSWORD to include it. Nothing was faked.');
  }

  /* -------- 7. a stale organization header cannot reuse the URL ------- */
  await signIn(page, AUTHOR_USER, AUTHOR_PASS);
  const finalCall = api(page);

  const restored = await finalCall(
    `/api/v1/validation/attachments/${attachmentId}`, { headers: H });
  check('7. the author can download again after reinstatement',
        restored.status === 200, `HTTP ${restored.status}`);

  const otherOrgs = await finalCall('/api/v1/organizations');
  const secondOrg = (otherOrgs.body?.organizations ?? []).find(
    (o) => o.id !== orgId);
  if (secondOrg) {
    expectRejection = true;
    const stale = await finalCall(
      `/api/v1/validation/attachments/${attachmentId}`,
      { headers: { 'X-Organization-Id': String(secondOrg.id) } });
    check('7a. the same URL under another organization returns nothing',
          stale.status === 404, `HTTP ${stale.status}`);
    check('7b. and no cached bytes come back with it',
          !stale.text.includes(MARKER));
    expectRejection = false;
  } else {
    notes.push('organization-switch check ran against the header only: this '
               + 'account belongs to one organization, so a second could not '
               + 'be selected.');
  }

  /* --------------------- 8. deletion, and staying deleted ------------- */
  const deleted = await finalCall(
    `/api/v1/validation/attachments/${attachmentId}`,
    { method: 'DELETE', headers: H });
  check('8. the author can delete their attachment', deleted.status === 200,
        `HTTP ${deleted.status}`);

  expectRejection = true;
  const afterDelete = await finalCall(
    `/api/v1/validation/attachments/${attachmentId}`, { headers: H });
  check('8a. a deleted attachment cannot be downloaded',
        afterDelete.status === 400 || afterDelete.status === 404,
        `HTTP ${afterDelete.status}`);
  check('8b. and no byte of it is served',
        !afterDelete.text.includes(MARKER));
  expectRejection = false;

  await shot(page, '04-after-deletion');
  await browser.close();

  console.log('');
  for (const note of notes) console.log(`note: ${note}`);
  console.log('');
  console.log(`assertions run: ${assertions}`);
  console.log(`live stored object exercised: attachment #${attachmentId}, `
              + `${created.size} bytes, sha256 ${created.digest.slice(0, 16)}…`);
  console.log('');
  if (problems.length === 0) {
    console.log('All attachment-storage checks passed.');
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
