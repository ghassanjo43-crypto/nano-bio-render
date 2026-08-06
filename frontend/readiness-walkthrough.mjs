/**
 * Browser walkthrough of the Scientific Readiness Framework.
 *
 * What this checks that the unit tests cannot: that the page is wired to the
 * *running* backend. The vitest suite stubs `fetch`, so it would pass happily
 * against a server that does not serve these routes at all — which is exactly
 * how an earlier stale-process 404 escaped verification. Hence the preflight
 * below, which fails loudly rather than letting a stale server look healthy.
 *
 * Walked:
 *   1. the six areas render from a real assessment;
 *   2. a blocked area shows its blocking issue and its percentage together;
 *   3. the not-accreditation notice is present;
 *   4. provenance is broken down by how each value is known;
 *   5. the Builder and Step 3 both link here;
 *   6. a demonstration study reads as illustrative, 0%, blocked;
 *   7. DEFECT-P1-A — real measured data assessed by the running engine stops at
 *      E2, and E3-E6 are declared unreachable;
 *   8. DEFECT-P1-B — the live API refuses a malformed measurement date and
 *      accepts a real one.
 *
 * Steps 7 and 8 go through the API rather than the page on purpose. Both
 * defects are backend behaviour, and the vitest suite stubs `fetch`, so only a
 * live call can show that the *running* engine no longer overclaims and that
 * the *running* schema rejects a bad date.
 *
 * Side effect: step 8 leaves one scientific record (`physical_diameter`, on the
 * walkthrough account's first study) in the development database. The write is
 * an upsert, so repeated runs do not accumulate.
 */

import { chromium } from 'playwright';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const OUT = resolve('../docs/screenshots');
// Supplied by the environment; the run stops with instructions if either
// variable is missing. See walkthrough-credentials.mjs.
const { user: USER, pass: PASS } = walkthroughCredentials();

mkdirSync(OUT, { recursive: true });

const problems = [];
const notes = [];
const log = (l, v) => console.log(`${l.padEnd(56, '.')} ${v}`);
function check(l, ok, detail = '') {
  log(l, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${l}${detail ? `: ${detail}` : ''}`);
}

async function shot(page, name) {
  await page.screenshot({ path: resolve(OUT, `readiness-${name}.png`),
                          fullPage: true });
}

/**
 * Confirm the RUNNING server serves the readiness routes before trusting any
 * page result. A server started before these routes existed answers /health
 * perfectly well and 404s everything that matters.
 */
async function preflight() {
  // Probed through the same origin the app uses, so this also proves the dev
  // proxy is routing. Unauthenticated, 401 is the *success* signal: the route
  // exists and is protected. 404 means the running server predates it.
  const probes = [
    '/api/v1/science/vocabulary',
    '/api/v1/science/studies/1/readiness',
  ];
  let ok = true;
  for (const path of probes) {
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
    console.log('\nPROBLEMS:');
    for (const p of problems) console.log(` - ${p}`);
    console.log('\nAborted: the running server does not serve these routes. '
      + 'Restart it before trusting any page result.');
    process.exit(1);
  }

  const browser = await chromium.launch({
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  // Step 8 provokes a 422 on purpose, and the browser logs every 4xx to the
  // console. Suppressed only while `expectRejection` is set, so an unexpected
  // 422 anywhere else in the run is still reported.
  let expectRejection = false;
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    if (t.includes('favicon') || t.includes('401')) return;
    if (expectRejection && /\b4\d\d\b/.test(t)) return;
    problems.push(`console error: ${t.slice(0, 140)}`);
  });

  const apiFailures = [];
  page.on('response', (r) => {
    const u = r.url();
    if (u.includes('/api/v1/science/') && r.status() >= 400) {
      apiFailures.push(`${r.status()} ${u.replace(APP, '')}`);
    }
  });

  await page.goto(`${APP}/login`);
  await page.fill('#username', USER);
  await page.fill('#password', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 15000 });
  log('signed in', 'ok');

  /* ------------------------------------------- 1. the dashboard loads --- */
  await page.goto(`${APP}/scientific-readiness`);
  await page.waitForSelector('[data-testid="not-accreditation"]',
                             { timeout: 20000 });

  const noStudies = await page.getByText(/No saved studies/i).count();
  if (noStudies) {
    notes.push('the walkthrough account has no saved studies; '
      + 'area assertions were skipped');
    check('empty state offers a way to start a study',
          await page.getByTestId('start-a-study').count() > 0);
    await shot(page, 'empty');
  } else {
    await page.waitForSelector('[data-testid="readiness-areas"]',
                               { timeout: 20000 });

    const AREAS = ['structural_visualization', 'formulation_assessment',
                   'biological_targeting', 'pharmacokinetic_modelling',
                   'safety_assessment', 'cinematic_animation'];
    let present = 0;
    for (const a of AREAS) {
      if (await page.getByTestId(`area-${a}`).count()) present += 1;
    }
    check('all six areas render', present === 6, `${present}/6`);

    /* --------------------------- 2. percentage and status side by side --- */
    let sawBlocked = false;
    let sawPercentWithBlock = null;
    for (const a of AREAS) {
      const card = page.getByTestId(`area-${a}`);
      if (!await card.count()) continue;
      const text = await card.innerText();
      if (/Blocked|Outside model domain/i.test(text)) {
        sawBlocked = true;
        const pct = await page.getByTestId(`percent-${a}`).innerText();
        sawPercentWithBlock = `${a} ${pct.trim()}`;
      }
    }
    check('at least one area is blocked (nothing is ready by default)',
          sawBlocked);
    if (sawPercentWithBlock) {
      notes.push(`blocked area shows its own percentage: ${sawPercentWithBlock}`);
    }

    /* ------------------------------------------ 4. provenance breakdown --- */
    const hasProvenance = await page.getByTestId('provenance-summary').count();
    if (hasProvenance) {
      const t = await page.getByTestId('provenance-summary').innerText();
      notes.push(`provenance: ${t.replace(/\s+/g, ' ').trim().slice(0, 120)}`);
      check('measured is not shown for a study with no measurements',
            !/^Measured/.test(t) || /Measured/.test(t));
    } else {
      notes.push('no provenance summary (study has no records at all)');
    }

    /* ------------------------------------------------- evidence level --- */
    const ev = await page.getByTestId('evidence-formulation_assessment')
      .innerText().catch(() => '');
    if (ev) notes.push(`formulation evidence level: ${ev.trim()}`);

    await shot(page, 'dashboard');
  }

  /* ------------------------------------- 3. the disclaimer is present --- */
  const notice = await page.getByTestId('not-accreditation').innerText();
  check('states it is not regulatory approval', /not regulatory approval/i
    .test(notice));
  check('states it is not clinical validation', /clinical validation/i
    .test(notice));
  check('states it is not accreditation', /scientific accreditation/i
    .test(notice));
  check('states a ready study can still be wrong',
        /fully ready and still be scientifically wrong/i.test(notice));

  /* ----------------------------------- engine and dictionary versions --- */
  const meta = await page.getByTestId('engine-meta').innerText()
    .catch(() => '');
  if (meta) {
    check('reports the rules-engine version it was assessed under',
          /readiness-rules-/.test(meta), meta.slice(0, 80));
    check('reports the dictionary version',
          /data-dictionary-/.test(meta), meta.slice(0, 80));
  }

  /* --------------------------------------------- 5. it is connected in --- */
  const navLink = page.getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: /Scientific Readiness/i });
  check('reachable from the sidebar', await navLink.count() > 0);
  if (await navLink.count()) {
    check('sidebar entry is marked active on the page',
          await navLink.first().getAttribute('aria-current') === 'page');
  }

  await page.goto(`${APP}/builder`);
  await page.waitForLoadState('networkidle');
  check('the 3D Builder links to readiness',
        await page.getByTestId('builder-to-readiness').count() > 0);

  // Step 3 renders its configuration section only for an active draft, so the
  // link has to be reached through the workflow rather than by deep link.
  await page.goto(`${APP}/workflow/disease`);
  await page.waitForSelector('select#disease', { timeout: 20000 });
  await page.selectOption('select#disease', 'Breast Cancer');
  await page.selectOption('select#subtype', 'HER2-enriched (ER-, PR-, HER2+)');
  await page.selectOption('select#drug', 'Trastuzumab (Herceptin)');
  await page.getByTestId('pathway-continue').click();
  await page.waitForSelector('#size_nm', { timeout: 20000 });
  await page.fill('#size_nm', '100');
  await page.fill('#charge_mv', '-5');
  await page.fill('#encapsulation_percent', '85');
  // Step 3 guards on the workflow having advanced, not merely on the fields
  // being filled — a deep link with unsaved values redirects back to step 1.
  await page.getByTestId('pathway-continue').click();
  await page.getByTestId('pathway-continue').click();
  await page.waitForURL(/\/workflow\/review/, { timeout: 20000 })
    .catch(() => {});
  await page.waitForSelector('[data-testid="step3-to-readiness"]',
                             { timeout: 20000 }).catch(() => {});
  check('Step 3 links to readiness',
        await page.getByTestId('step3-to-readiness').count() > 0);

  /* ------------------------------- 6. demonstration study is honest ---- */
  await page.goto(`${APP}/scientific-readiness`);
  await page.waitForSelector('[data-testid="not-accreditation"]',
                             { timeout: 20000 });
  // The selector only appears once the study list resolves; probing straight
  // after the disclaimer renders finds nothing and skips this silently.
  const select = page.locator('#sr-study');
  await select.waitFor({ timeout: 20000 }).catch(() => {});
  if (await select.count()) {
    let sawDemo = false;
    const options = await select.locator('option').allTextContents();
    notes.push(`studies available: ${options.length}`);
    for (let i = 0; i < options.length; i += 1) {
      await select.selectOption({ index: i });
      await page.waitForTimeout(600);
      await page.waitForSelector('[data-testid="readiness-areas"]',
                                 { timeout: 20000 }).catch(() => {});
      const legacy = await page.getByTestId('legacy-notice').count();
      if (legacy) {
        const t = await page.getByTestId('legacy-notice').innerText();
        if (/demonstration study/i.test(t)) {
          check('a demonstration study is declared illustrative',
                /illustrative/i.test(t) && /no real material/i.test(t));
          const pct = await page.getByTestId('percent-formulation_assessment')
            .innerText().catch(() => '');
          check('a demonstration study scores 0%', /0%/.test(pct), pct);
          await shot(page, 'demo-study');
          sawDemo = true;
          break;
        }
      }
    }
    if (!sawDemo) {
      notes.push('no demonstration study in this account; '
        + 'the illustrative-provenance assertion did not run');
    }
  } else {
    notes.push('study selector never appeared; step 6 did not run');
  }

  /* ------------------------- 7 & 8. the two corrected defects, live ---- */
  // Issued from the page so the session cookie travels with them.
  //
  // Step 8 deliberately provokes a 4xx, which the response listener above
  // records like any other. Everything logged from here on is therefore
  // examined separately: the unsolicited-failure check keeps its original
  // scope, and the deliberate rejection is asserted to be the *only* thing
  // these probes added — so a genuine new failure among them still surfaces.
  const failuresBeforeProbes = apiFailures.length;
  const api = (path, init) => page.evaluate(
    async ([p, i]) => {
      const response = await fetch(p, i ?? undefined);
      let body = null;
      try { body = await response.json(); } catch { body = null; }
      return { status: response.status, body };
    }, [path, init ?? null]);

  const runs = await api('/api/v1/runs');
  const studyId = runs.body?.runs?.[0]?.id ?? null;

  if (studyId === null) {
    notes.push('no study on the walkthrough account; steps 7 and 8 did not run');
  } else {
    const put = (fieldId, payload) => api(
      `/api/v1/science/studies/${studyId}/records/${fieldId}`,
      { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload) });

    /* ---- 8. a malformed measurement date is refused ------------------- */
    expectRejection = true;
    const bad = await put('physical_diameter', {
      status: 'measured', value: '100', unit: 'nm',
      measurement_method: 'cryo-TEM', measured_on: '13/05/2026',
    });
    expectRejection = false;
    check('a malformed measurement date is refused',
          bad.status === 422 || bad.status === 400, `HTTP ${bad.status}`);
    const badDetail = JSON.stringify(bad.body ?? {});
    check('the refusal names the expected date form',
          /YYYY-MM-DD/.test(badDetail), badDetail.slice(0, 140));
    check('the refusal carries no readiness result',
          !/"areas"/.test(badDetail));

    /* ---- 8b. a real ISO date is accepted ------------------------------ */
    const good = await put('physical_diameter', {
      status: 'measured', value: '100', unit: 'nm',
      measurement_method: 'cryo-TEM', measured_on: '2026-08-01',
    });
    check('a real ISO measurement date is accepted', good.status === 200,
          `HTTP ${good.status}`);

    /* ---- 8c. the stored record loads back ----------------------------- */
    const records = await api(`/api/v1/science/studies/${studyId}/records`);
    const stored = (records.body?.records ?? [])
      .find((r) => r.field_id === 'physical_diameter');
    check('a study with a measurement date still loads',
          records.status === 200 && stored !== undefined,
          `HTTP ${records.status}`);
    if (stored) {
      check('the stored date is normalised, not free text',
            stored.measured_on === '2026-08-01', String(stored.measured_on));
    }

    /* ---- 7. measured data does not reach a validation level ----------- */
    // Every field structural visualisation *requires*, recorded as measured
    // with a stated method. This is the exact input that returned E3 —
    // "retrospectively validated" — before the correction, so a live E2 here
    // is the defect being absent rather than merely untested.
    const MEASURED_STRUCTURAL = [
      ['nanoparticle_class', { value: 'lipid' }],
      ['architecture', { value: 'liposome' }],
      ['physical_diameter', { value: '100', unit: 'nm' }],
      ['shell_material', { value: 'DSPC/cholesterol bilayer' }],
      ['morphology', { value: 'spherical, unilamellar' }],
      ['coating_thickness', { value: '5', unit: 'nm' }],
      ['porosity', { value: '0', unit: '%' }],
      ['payload_location', { value: 'aqueous_core' }],
    ];
    let written = 0;
    for (const [fieldId, payload] of MEASURED_STRUCTURAL) {
      const response = await put(fieldId, {
        status: 'measured', measurement_method: 'cryo-TEM',
        measured_on: '2026-08-01', ...payload,
      });
      if (response.status === 200) written += 1;
      else notes.push(`could not record ${fieldId}: HTTP ${response.status} `
        + `${JSON.stringify(response.body).slice(0, 120)}`);
    }
    check('a fully measured area can be recorded',
          written === MEASURED_STRUCTURAL.length,
          `${written}/${MEASURED_STRUCTURAL.length}`);

    const assessment = await api(
      `/api/v1/science/studies/${studyId}/readiness`);
    const areas = assessment.body?.areas ?? [];
    const levels = areas.map((a) => a.evidence_level);
    check('the live engine assessed the study', areas.length === 6,
          `${areas.length} areas`);
    // The Phase 1 defect fix, restated so it survives the registry existing:
    // an area may be at E3 ONLY where approved registry evidence supports it,
    // and every area without such evidence is still capped at E2. Measured
    // data alone still promotes nothing.
    const evidence = await api(
      `/api/v1/validation/studies/${studyId}/evidence`);
    const promoted = new Set(
      Object.entries(evidence.body?.by_purpose ?? {})
        .filter(([, v]) => v.level === 'E3')
        .map(([k]) => k));
    notes.push(`purposes with approved E3: ${[...promoted].join(', ') || 'none'}`);

    const unbacked = areas.filter(
      (a) => ['E3', 'E4', 'E5', 'E6'].includes(a.evidence_level)
             && !promoted.has(a.area));
    check('no area reaches E3 without approved registry evidence',
          unbacked.length === 0,
          unbacked.map((a) => `${a.area}=${a.evidence_level}`).join(','));

    check('every area without approved evidence stays at E2 or below',
          areas.filter((a) => !promoted.has(a.area))
            .every((a) => ['E0', 'E1', 'E2'].includes(a.evidence_level)),
          levels.join(','));

    check('no area ever reaches E4, E5 or E6',
          levels.every((l) => !['E4', 'E5', 'E6'].includes(l)),
          levels.join(','));
    // Phase 2 Milestone 1 delivered the registry, so this flipped together
    // with the implementation behind it.
    check('the assessment declares the validation registry available',
          assessment.body?.validation_registry_available === true);
    check('the assessment declares E3 as the ceiling',
          assessment.body?.max_attainable_evidence_level === 'E3',
          String(assessment.body?.max_attainable_evidence_level));
    check('every area explains its evidence level',
          areas.length > 0 && areas.every(
            (a) => (a.evidence_level_rationale ?? '').length > 60));
    notes.push(`live evidence levels: ${levels.join(', ')}`);

    const structural = areas.find(
      (a) => a.area === 'structural_visualization');
    if (structural) {
      // The assertion this whole step exists for.
      // Structural visualization has no approved experiment in any run of
      // this script, so it is the clean case: fully measured, still E2.
      check('a fully measured area with no approved experiment stays at E2',
            structural.evidence_level === 'E2', structural.evidence_level);
      check('a measured area is told a measurement is not a validation',
            (structural.warnings ?? []).some(
              (w) => w.code === 'measurement_is_not_validation'));
      check('the ceiling is explained where it bites',
            /Experimental Validation Registry/.test(
              structural.evidence_level_rationale ?? ''),
            (structural.evidence_level_rationale ?? '').slice(0, 90));
    }

    /* ---- 7b. the vocabulary says which levels are unreachable --------- */
    const vocab = await api('/api/v1/science/vocabulary');
    const byId = Object.fromEntries(
      (vocab.body?.evidence_levels ?? []).map((e) => [e.id, e]));
    // E3 became attainable with the registry. E4-E6 did not: they need
    // prospective in-vitro, in-vivo and clinical evidence that Milestone 1
    // does not record.
    check('E4 to E6 remain unattainable',
          ['E4', 'E5', 'E6'].every((id) => byId[id]?.attainable === false),
          Object.keys(byId).join(','));
    check('E0 to E3 are attainable',
          ['E0', 'E1', 'E2', 'E3'].every((id) => byId[id]?.attainable === true));
    check('each validation level states what it requires',
          ['E3', 'E4', 'E5', 'E6'].every(
            (id) => (byId[id]?.requirement ?? '').length > 40));
  }

  const unsolicited = apiFailures.slice(0, failuresBeforeProbes);
  check('no failing readiness API calls', unsolicited.length === 0,
        unsolicited.join('; '));

  const provoked = apiFailures.slice(failuresBeforeProbes);
  check('the only rejected call is the malformed date, and it was rejected',
        provoked.length === 1 && /^4\d\d /.test(provoked[0]),
        provoked.join('; ') || 'nothing was rejected');

  await browser.close();

  console.log('');
  for (const n of notes) console.log(`note: ${n}`);
  console.log('');
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log(` - ${p}`);
  if (problems.length) process.exitCode = 1;
}

main().catch((e) => { console.error(e); process.exit(1); });
