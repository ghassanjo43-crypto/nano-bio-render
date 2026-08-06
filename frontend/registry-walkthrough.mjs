/**
 * Live end-to-end walkthrough of the Experimental Validation Registry.
 *
 * What this proves that no other suite can
 * ----------------------------------------
 * The vitest suite stubs `fetch`, so it would pass against a backend that does
 * not serve these routes at all. The pytest suite exercises the service
 * directly, so it would pass against a frontend that never calls it. Only this
 * script drives a real browser against a running server through the whole
 * scientific workflow — create, complete, attach, submit, review, approve —
 * and checks that E3 lands where it should and nowhere else.
 *
 * Two users, and they matter
 * --------------------------
 * The performer and the reviewer are different accounts, because an experiment
 * cannot be approved by whoever performed it. The script signs out and back in
 * to switch. A single-user run would silently skip the most important control
 * in the registry.
 *
 * Credentials come from the environment, and the accounts are created by the
 * operator before the run — see `walkthrough-credentials.mjs`. Nothing here is
 * embedded.
 */

import { chromium } from 'playwright';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const OUT = resolve('../docs/screenshots');
mkdirSync(OUT, { recursive: true });

// The performer. The reviewer is a SECOND account, supplied separately so the
// independence rule is genuinely exercised rather than assumed.
const { user: USER, pass: PASS } = walkthroughCredentials();
const REVIEWER_USER = process.env.NANOBIO_REVIEWER_USER;
const REVIEWER_PASS = process.env.NANOBIO_REVIEWER_PASSWORD;

if (!REVIEWER_USER || !REVIEWER_PASS) {
  console.error(`
The registry walkthrough needs a SECOND account to review the experiment,
because an experiment cannot be approved by whoever performed it.

  PowerShell:
    $env:NANOBIO_REVIEWER_USER = 'walkthrough_reviewer'
    $env:NANOBIO_REVIEWER_PASSWORD = '<the reviewer password>'

Create it against the development database with:

    python nanobio_studio_backend/scripts/create_admin.py \\
        --username walkthrough_reviewer --role researcher

Nothing was run and no browser was launched.
`);
  process.exit(2);
}

const problems = [];
const notes = [];
const log = (l, v) => console.log(`${l.padEnd(58, '.')} ${v}`);
function check(label, ok, detail = '') {
  log(label, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
}

async function shot(page, name) {
  await page.screenshot({ path: resolve(OUT, `registry-${name}.png`),
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
  await page.goto(`${APP}/login`);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 20000 });
}

async function signOut(page) {
  // Clearing cookies is deterministic; the menu-driven sign-out is covered by
  // the navigation walkthrough and is not what this script is testing.
  await page.context().clearCookies();
}

/** Confirm the running server serves the registry before trusting anything. */
async function preflight() {
  let ok = true;
  for (const path of ['/api/v1/validation/vocabulary',
                      '/api/v1/validation/experiments']) {
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

  const call = api(page);

  /* ---------------------------------------------- 1. sign in ---------- */
  await signIn(page, USER, PASS);
  check('1. performer signs in', true);

  /* --------------------------------- 2. create or select a study ------ */
  const runs = await call('/api/v1/runs');
  let studyId = runs.body?.runs?.[0]?.id ?? null;
  if (studyId === null) {
    // A clean installation has none. Creating one here is part of what this
    // walkthrough is proving: a fresh install can be driven end to end.
    const made = await call('/api/v1/runs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Acceptance walkthrough study',
        disease: 'Breast Cancer',
        subtype: 'HER2-enriched (ER-, PR-, HER2+)',
        drug: 'Trastuzumab (Herceptin)',
        design_inputs: { size_nm: 100, charge_mv: -5,
                         encapsulation_percent: 85 },
        pathway: 'research_design',
      }),
    });
    studyId = made.body?.id ?? null;
    check('2. a study is created on a clean installation', studyId !== null,
          `HTTP ${made.status} ${JSON.stringify(made.body).slice(0, 160)}`);
  } else {
    check('2. a study is available', true, `study ${studyId}`);
  }
  if (studyId === null) {
    console.log('Aborted: no study could be created.');
    await browser.close();
    process.exit(1);
  }

  /* -------------------- 3. candidate + immutable candidate version ---- */
  const stamp = Date.now().toString(36);
  const candidate = await call('/api/v1/validation/candidates', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ study_id: studyId, code: `CAND-${stamp}`,
                           name: 'Walkthrough liposome' }),
  });
  check('3a. candidate created', candidate.status === 200,
        `HTTP ${candidate.status}`);

  const cversion = await call(
    `/api/v1/validation/candidates/${candidate.body?.id}/versions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        design_inputs: { size_nm: 100, charge_mv: -5,
                         encapsulation_percent: 85 },
        note: 'Frozen for the acceptance walkthrough.',
      }),
    });
  check('3b. candidate version frozen with a checksum',
        cversion.status === 200 && typeof cversion.body?.checksum === 'string'
        && cversion.body.checksum.length === 64,
        `HTTP ${cversion.status}`);
  const candidateVersionId = cversion.body?.id;

  /* ----------------------------- 4. create the in-vitro experiment ---- */
  const created = await call('/api/v1/validation/experiments', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_version_id: candidateVersionId,
      subtype: 'cytotoxicity', purpose: 'safety_assessment',
      title: 'Walkthrough cytotoxicity of candidate A',
      code: `EXP-${stamp}`,
    }),
  });
  check('4. in-vitro experiment created', created.status === 200,
        `HTTP ${created.status}`);
  const experimentId = created.body?.experiment_id;
  const versionId = created.body?.version_id;

  // An incompatible purpose must be refused by the SERVER, whatever the
  // interface offers.
  expectRejection = true;
  const wrongPurpose = await call('/api/v1/validation/experiments', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_version_id: candidateVersionId,
      subtype: 'cytotoxicity', purpose: 'structural_visualization',
      title: 'Should be refused', code: `EXP-BAD-${stamp}`,
    }),
  });
  expectRejection = false;
  check('4b. an incompatible purpose is refused by the backend',
        wrongPurpose.status === 400, `HTTP ${wrongPurpose.status}`);

  /* -------------- 5. protocol, controls, replicates, measurements ----- */
  const patched = await call(`/api/v1/validation/versions/${versionId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scientific_question: 'Does candidate A reduce viability in SK-BR-3?',
      hypothesis: 'Viability falls to 50% or below at 10 ug/mL.',
      laboratory_name: 'Walkthrough cell culture laboratory',
      investigator_name: 'Walkthrough Investigator',
      investigator_org: 'NanoBio Studio Research',
      protocol_identifier: 'PROT-CYTO-WT', protocol_version: '1.0',
      biological_model: 'Human breast adenocarcinoma',
      cell_line: 'SK-BR-3', cell_source: 'ATCC HTB-30',
      cell_authentication_status: 'STR authenticated',
      assay_method: 'MTT viability assay, 48 h exposure',
      control_positive: 'Doxorubicin 1 uM',
      control_negative: 'Untreated cells',
      control_vehicle: '0.1% DMSO',
      biological_replicates: 3, technical_replicates: 3,
      replicate_justification: 'Three independent preparations.',
      statistical_method: 'One-way ANOVA with Dunnett correction',
      deviations: 'None', exclusions: 'None', missing_data: 'None',
      disclosures_confirmed: true,
      investigator_conclusion: 'Predefined criteria met.',
      provenance_declaration: 'Generated in-house; raw plate reads attached.',
      acceptance_criteria_met: true,
      requested_level: 'E3',
      acceptance_criteria_json: JSON.stringify([{
        endpoint: 'viability_percent', comparator: '<=', value: 50, unit: '%',
        description: 'Viability at 10 ug/mL must be at or below 50%.',
      }]),
    }),
  });
  check('5a. protocol, controls and replicates recorded',
        patched.status === 200, `HTTP ${patched.status}`);

  const measured = await call(
    `/api/v1/validation/versions/${versionId}/measurements`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: [41.0, 44.5, 39.2].map((v, i) => ({
        endpoint_name: 'viability_percent', sample_group: '10 ug/mL',
        replicate_id: `R${i + 1}`, result_numeric: v, result_unit: '%',
        method: 'MTT',
      })) }),
    });
  check('5b. subtype-specific measurements recorded',
        measured.status === 200 && measured.body?.recorded === 3,
        `HTTP ${measured.status}`);

  /* ------------------------- 6. upload and download an attachment ----- */
  const upload = await page.evaluate(async ([vid]) => {
    const csv = 'endpoint,replicate,value\nviability_percent,R1,41.0\n';
    const form = new FormData();
    form.append('file', new File([csv], 'plate-reads.csv',
                                 { type: 'text/csv' }));
    const r = await fetch(
      `/api/v1/validation/versions/${vid}/attachments?category=raw_data`,
      { method: 'POST', body: form });
    return { status: r.status, body: await r.json().catch(() => null) };
  }, [versionId]);
  check('6a. a permitted attachment uploads',
        upload.status === 200 && upload.body?.checksum_sha256?.length === 64,
        `HTTP ${upload.status}`);

  const attachmentId = upload.body?.id;
  const download = await page.evaluate(async ([aid]) => {
    const r = await fetch(`/api/v1/validation/attachments/${aid}`);
    return {
      status: r.status,
      disposition: r.headers.get('content-disposition'),
      nosniff: r.headers.get('x-content-type-options'),
      text: await r.text(),
    };
  }, [attachmentId]);
  check('6b. the attachment downloads with its bytes intact',
        download.status === 200 && download.text.includes('viability_percent'),
        `HTTP ${download.status}`);
  check('6c. the download is forced, not rendered inline',
        (download.disposition ?? '').startsWith('attachment')
        && download.nosniff === 'nosniff');
  check('6d. no filesystem path is disclosed',
        !/[A-Za-z]:\\|\/var\/|\/home\//.test(
          JSON.stringify(upload.body ?? {})));

  /* ------------------------- 7. unsafe attachment is rejected --------- */
  expectRejection = true;
  const hostile = await page.evaluate(async ([vid]) => {
    const out = {};
    // An executable wearing a .csv extension.
    const exe = new Uint8Array([0x4d, 0x5a, 0x90, 0x00, 0, 0, 0, 0]);
    const f1 = new FormData();
    f1.append('file', new File([exe], 'innocent.csv', { type: 'text/csv' }));
    const r1 = await fetch(
      `/api/v1/validation/versions/${vid}/attachments?category=raw_data`,
      { method: 'POST', body: f1 });
    out.executable = { status: r1.status,
                       body: await r1.json().catch(() => null) };

    // A traversal filename.
    const f2 = new FormData();
    f2.append('file', new File(['a,b\n1,2\n'], '../../../etc/passwd.csv',
                               { type: 'text/csv' }));
    const r2 = await fetch(
      `/api/v1/validation/versions/${vid}/attachments?category=raw_data`,
      { method: 'POST', body: f2 });
    out.traversal = { status: r2.status,
                      body: await r2.json().catch(() => null) };

    // A disallowed type.
    const f3 = new FormData();
    f3.append('file', new File(['x'], 'script.sh',
                               { type: 'application/x-sh' }));
    const r3 = await fetch(
      `/api/v1/validation/versions/${vid}/attachments?category=raw_data`,
      { method: 'POST', body: f3 });
    out.badType = { status: r3.status,
                    body: await r3.json().catch(() => null) };
    return out;
  }, [versionId]);
  expectRejection = false;

  check('7a. an executable named .csv is rejected',
        hostile.executable.status === 400
        && hostile.executable.body?.error === 'executable_content',
        `HTTP ${hostile.executable.status} ${hostile.executable.body?.error}`);
  check('7b. a disallowed type is rejected',
        hostile.badType.status === 400,
        `HTTP ${hostile.badType.status} ${hostile.badType.body?.error}`);
  check('7c. a traversal filename is reduced, not stored as a path',
        hostile.traversal.status === 200
        && hostile.traversal.body?.original_filename === 'passwd.csv',
        String(hostile.traversal.body?.original_filename));

  /* ----------------------------------- 8. submit ---------------------- */
  const submitted = await call(
    `/api/v1/validation/versions/${versionId}/submit`, { method: 'POST' });
  check('8a. the experiment submits', submitted.status === 200,
        `HTTP ${submitted.status}`);

  expectRejection = true;
  const editAfterSubmit = await call(
    `/api/v1/validation/versions/${versionId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hypothesis: 'changed after submission' }),
    });
  check('8b. a submitted version can no longer be edited',
        editAfterSubmit.status === 403, `HTTP ${editAfterSubmit.status}`);

  const selfReview = await call(
    `/api/v1/validation/versions/${versionId}/review`, { method: 'POST' });
  expectRejection = false;
  check('8c. the performer cannot review their own experiment',
        selfReview.status === 403, `HTTP ${selfReview.status}`);

  await page.goto(`${APP}/validation`);
  await page.waitForSelector('[data-testid="registry-scope-note"]',
                             { timeout: 20000 });
  await shot(page, '01-registry');

  /* ------------------------- 9. review as a different user ------------ */
  await signOut(page);
  await signIn(page, REVIEWER_USER, REVIEWER_PASS);
  const call2 = api(page);
  check('9a. an independent reviewer signs in', true);

  const review = await call2(
    `/api/v1/validation/versions/${versionId}/review`, { method: 'POST' });
  check('9b. the reviewer begins review', review.status === 200,
        `HTTP ${review.status}`);

  /* ------------------------------------ 10. approve ------------------- */
  const decision = await call2(
    `/api/v1/validation/versions/${versionId}/decision`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: 'approve',
                             comments: 'Gates satisfied; criteria met.' }),
    });
  check('10a. the reviewer approves', decision.status === 200,
        `HTTP ${decision.status} ${decision.body?.error ?? ''}`);
  check('10b. approval grants E3, and only E3',
        decision.body?.approved_level === 'E3',
        String(decision.body?.approved_level));
  check('10c. every eligibility gate passed',
        (decision.body?.eligibility?.failed_gates ?? ['unknown']).length === 0,
        JSON.stringify(decision.body?.eligibility?.failed_gates));

  /* -------------------------- 11. approved is immutable --------------- */
  expectRejection = true;
  const editApproved = await call2(
    `/api/v1/validation/versions/${versionId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ investigator_conclusion: 'rewritten' }),
    });
  check('11a. an approved version cannot be edited',
        editApproved.status === 403, `HTTP ${editApproved.status}`);

  const removeEvidence = await call2(
    `/api/v1/validation/attachments/${attachmentId}`, { method: 'DELETE' });
  expectRejection = false;
  check('11b. evidence cannot be removed from an approved version',
        removeEvidence.status === 400 || removeEvidence.status === 403,
        `HTTP ${removeEvidence.status}`);

  /* --------------- 12/13. only the claimed purpose reaches E3 --------- */
  const evidence = await call2(
    `/api/v1/validation/studies/${studyId}/evidence`);
  const byPurpose = evidence.body?.by_purpose ?? {};
  check('12. the claimed purpose reaches E3',
        byPurpose.safety_assessment?.level === 'E3',
        JSON.stringify(Object.keys(byPurpose)));

  const others = ['structural_visualization', 'formulation_assessment',
                  'biological_targeting', 'pharmacokinetic_modelling',
                  'cinematic_animation'];
  check('13a. no unrelated purpose reaches E3',
        others.every((p) => byPurpose[p]?.level !== 'E3'));

  // Readiness is queried as the study's OWNER. The registry endpoints
  // deliberately do not check study ownership — a reviewer has to be able to
  // see work they did not do — but Scientific Readiness does, so asking as the
  // reviewer returns 404 and would leave these assertions reading an empty
  // body rather than testing anything.
  await signOut(page);
  await signIn(page, USER, PASS);
  const call3 = api(page);

  const readiness = await call3(
    `/api/v1/science/studies/${studyId}/readiness`);
  const areas = readiness.body?.areas ?? [];
  check('13b0. readiness is available to the study owner',
        areas.length === 6, `HTTP ${readiness.status}, ${areas.length} areas`);
  const safety = areas.find((a) => a.area === 'safety_assessment');
  check('13b. Scientific Readiness shows E3 for that area only',
        safety?.evidence_level === 'E3', String(safety?.evidence_level));
  check('13c. every other area is unchanged at E2 or below',
        areas.filter((a) => a.area !== 'safety_assessment')
          .every((a) => ['E0', 'E1', 'E2'].includes(a.evidence_level)),
        areas.map((a) => `${a.area}=${a.evidence_level}`).join(' '));
  check('13d. the readiness rationale names the registry',
        (safety?.evidence_level_rationale ?? '')
          .includes('Experimental Validation Registry'));
  notes.push(`evidence levels: ${areas.map((a) => a.evidence_level).join(', ')}`);

  /* ------------------------ 14. version and audit histories ----------- */
  await page.goto(`${APP}/validation/experiments/${experimentId}`);
  await page.waitForSelector('[data-testid="section-details"]',
                             { timeout: 20000 });
  check('14a. the experiment detail page renders',
        await page.getByTestId('detail-e3').count() > 0);
  // The verdict arrives on a second request; wait for the badge to settle
  // rather than reading it the instant the section renders.
  let e3Badge = '';
  for (let i = 0; i < 40; i += 1) {
    e3Badge = await page.getByTestId('detail-e3').innerText().catch(() => '');
    if (e3Badge.includes('E3 eligible')) break;
    await page.waitForTimeout(250);
  }
  check('14b. the page shows E3 eligible',
        e3Badge.includes('E3 eligible'), e3Badge.trim());

  await page.getByRole('tab', { name: 'Version history' }).click();
  await page.waitForSelector('[data-testid="section-versions"]',
                             { timeout: 10000 });
  check('14c. version history displays',
        await page.getByTestId('version-1').count() > 0);

  await page.getByRole('tab', { name: 'Audit history' }).click();
  await page.waitForSelector('[data-testid="section-audit"]',
                             { timeout: 10000 });
  const auditRows = await page.locator('[data-testid^="audit-"]').count();
  check('14d. audit history displays the lifecycle',
        auditRows >= 5, `${auditRows} event(s)`);

  await page.getByRole('tab', { name: 'Evidence decision' }).click();
  await page.waitForSelector('[data-testid="section-evidence"]',
                             { timeout: 10000 });
  check('14e. the evidence decision shows the gates and ruleset',
        await page.getByTestId('ruleset-version').count() > 0);
  await shot(page, '02-experiment-approved');

  /* --------------------- 15. pathway controls and unsaved changes ----- */
  // Step 2 is gated on the therapeutic selection, which a clean installation
  // does not have. Complete step 1 first rather than deep-linking past a gate
  // that exists for a reason.
  await page.goto(`${APP}/workflow/disease`);
  await page.waitForSelector('select#disease', { timeout: 20000 });
  await page.selectOption('select#disease', 'Breast Cancer');
  await page.selectOption('select#subtype', 'HER2-enriched (ER-, PR-, HER2+)');
  await page.selectOption('select#drug', 'Trastuzumab (Herceptin)');
  await page.getByTestId('pathway-continue').click();
  await page.waitForSelector('#size_nm', { timeout: 20000 });
  check('15pre. step 1 completes and the pathway advances to step 2', true);

  await page.waitForSelector('[data-testid="pathway-nav"]', { timeout: 20000 });
  check('15a. pathway Back is present and labelled',
        await page.getByTestId('pathway-back').count() > 0);
  check('15b. Save & Continue is present',
        await page.getByTestId('pathway-continue').count() > 0);
  check('15c. Save & Exit is present',
        await page.getByTestId('pathway-save-exit').count() > 0);

  const beforeDirty = await page.evaluate(() => {
    const e = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(e);
    return e.defaultPrevented;
  });
  check('15d. a clean study raises no unsaved-change warning',
        beforeDirty === false);

  await page.fill('#size_nm', '137');
  const afterDirty = await page.evaluate(() => {
    const e = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(e);
    return e.defaultPrevented;
  });
  check('15e. editing arms the unsaved-change warning', afterDirty === true);

  await page.getByTestId('pathway-continue').click();
  await page.waitForSelector('h2:has-text("Targeting & Ligands")',
                             { timeout: 20000 });
  check('15f. Save & Continue advances along the pathway', true);

  const afterSave = await page.evaluate(() => {
    const e = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(e);
    return e.defaultPrevented;
  });
  check('15g. Save & Continue saved, disarming the warning',
        afterSave === false);

  await page.getByTestId('pathway-back').click();
  await page.waitForSelector('h2:has-text("Step 2")', { timeout: 20000 });
  const preserved = await page.inputValue('#size_nm');
  check('15h. Back follows the pathway and preserves the edit',
        preserved === '137', preserved);

  await page.getByTestId('pathway-save-exit').click();
  await page.waitForURL(/\/studies/, { timeout: 20000 });
  check('15i. Save & Exit returns to My Studies', true);
  await shot(page, '03-pathway');

  await browser.close();

  console.log('');
  for (const n of notes) console.log(`note: ${n}`);
  console.log('');
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log(` - ${p}`);
  if (problems.length) process.exitCode = 1;
}

main().catch((e) => { console.error('WALKTHROUGH FAILED:', e); process.exit(1); });
