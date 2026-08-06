/**
 * Browser walkthrough of Step 3 for IV trastuzumab.
 *
 * Why this exists
 * ---------------
 * Step 3 returned "The service returned HTTP 404" because the running uvicorn
 * process had been started before `api/routes/pk_routed.py` existed and was
 * launched without `--reload`. The source was correct; the running service was
 * not. No unit test can see that — checking `app.routes` in a fresh interpreter
 * inspects the source, not the process answering on port 8000.
 *
 * So this script asks the LIVE server first, and fails loudly if the routes are
 * missing from it, before touching the UI at all.
 *
 * Scenario (as specified):
 *   Breast Cancer / HER2-enriched / Trastuzumab (Herceptin)
 *   size 100 nm, zeta -5 mV, encapsulation 85%
 *
 * Expected: the model plan LOADS, and states that IV trastuzumab is not yet
 * operational because no reviewed parameter set exists — naming CL, Vc, Q, Vp —
 * with Run disabled and no rate constants requested.
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

const DISEASE = 'Breast Cancer';
const SUBTYPE = 'HER2-enriched (ER-, PR-, HER2+)';
const DRUG = 'Trastuzumab (Herceptin)';

mkdirSync(OUT, { recursive: true });

const problems = [];
const log = (label, value) =>
  console.log(`${label.padEnd(48, '.')} ${value}`);

function check(label, ok, detail = '') {
  log(label, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
}

/**
 * Preflight against the LIVE server. This is the check that would have caught
 * the stale-process 404 immediately.
 */
async function preflight(page) {
  // Probe the real paths the client uses, through the same origin the browser
  // uses, with the session cookie already set. `/openapi.json` is not proxied
  // by the dev server, so probing it would only ever return the SPA shell.
  const probes = [
    '/api/v1/pk/administration-routes',
    '/api/v1/pk/plan?therapeutic=Trastuzumab%20(Herceptin)&route=iv_infusion',
  ];

  for (const path of probes) {
    const status = await page.evaluate(async (p) => {
      const r = await fetch(p, { credentials: 'include' });
      return r.status;
    }, path);
    log(`live GET ${path.split('?')[0]}`, status);
    check(`live server serves ${path.split('?')[0]}`, status === 200,
          status === 404
            ? 'HTTP 404 — the running backend predates this route; restart uvicorn'
            : `HTTP ${status}`);
  }
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

  const failedRequests = [];
  const calls = [];
  page.on('request', (r) => { calls.push(r.url()); });
  page.on('response', (r) => {
    const u = r.url();
    if (u.includes('/api/v1/pk/') && !r.ok()) {
      failedRequests.push(`${r.status()} ${r.request().method()} ${u}`);
    }
  });
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));

  // ------------------------------------------------------------- sign in
  await page.goto(`${APP}/login`);
  await page.fill('#username', USER);
  await page.fill('#password', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 15000 });
  log('signed in', 'ok');

  await preflight(page);

  // -------------------------------------------------- step 1: indication
  await page.goto(`${APP}/workflow/disease`);
  await page.waitForSelector('select#disease');
  await page.selectOption('select#disease', DISEASE);
  await page.selectOption('select#subtype', SUBTYPE);
  await page.selectOption('select#drug', DRUG);
  log('step 1', `${DISEASE} / ${SUBTYPE} / ${DRUG}`);
  await page.getByTestId('pathway-continue').click();

  // ------------------------------------------------ step 2: formulation
  await page.waitForSelector('#size_nm');
  await page.fill('#size_nm', '100');
  await page.fill('#charge_mv', '-5');
  await page.fill('#encapsulation_percent', '85');
  log('step 2', 'size 100 nm, zeta -5 mV, encapsulation 85%');
  await page.screenshot({ path: `${OUT}/pk-01-step2.png`, fullPage: true });
  await page.getByTestId('pathway-continue').click();
  await page.getByTestId('pathway-continue').click();

  // ---------------------------------------------------- step 3: PK plan
  await page.waitForSelector('[data-testid="pk-inputs"]');
  // Wait for the route list to arrive before judging the panel's state. A
  // fixed pause here previously reported a phantom "service unavailable"
  // simply because the fetch had not resolved — the same class of mistake
  // that produced the original 404 diagnosis.
  await page.waitForFunction(() => {
    const sel = document.querySelector('select#pk-route');
    return sel instanceof HTMLSelectElement && sel.options.length > 1;
  }, { timeout: 10000 });

  const body = await page.locator('body').innerText();

  check('no HTTP 404 shown on Step 3',
        !/returned HTTP 404|Could not load the model plan/i.test(body));
  check('planning service is not reported unavailable',
        (await page.locator('[data-testid="pk-service-unavailable"]').count())
        === 0);

  // Select the intravenous infusion route.
  await page.selectOption('select#pk-route', 'iv_infusion');
  await page.waitForSelector('[data-testid="route-description"]');
  // The plan request is in flight; wait for its outcome rather than the clock.
  await page.waitForSelector(
    '[data-testid="pk-blocked"], [data-testid="pk-service-unavailable"]',
    { timeout: 10000 });

  const routeText = await page.locator('[data-testid="route-description"]')
    .innerText();
  check('k_abs is marked Not applicable for IV infusion',
        /Not applicable/i.test(routeText), routeText.slice(0, 80));
  check('IV infusion is not described as a depot',
        /no depot compartment/i.test(routeText));

  const blocked = page.locator('[data-testid="pk-blocked"]');
  check('a blocked plan is shown', (await blocked.count()) === 1);

  if (await blocked.count()) {
    const text = await blocked.innerText();
    check('states "Not yet operational for this therapeutic/route combination"',
          /Not yet operational for this therapeutic\/route combination/i
            .test(text), text.slice(0, 120));
    check('names the missing reviewed parameters CL, Vc, Q, Vp',
          /CL,\s*Vc,\s*Q,\s*Vp/.test(text), text.slice(0, 160));
    check('states nothing was substituted or borrowed',
          /No values have been substituted/i.test(text));
    log('blocked message', text.replace(/\n+/g, ' | ').slice(0, 150));
  }

  check('Run Simulation is not offered',
        (await page.locator('[data-testid="run-routed-simulation"]').count())
        === 0);
  check('no provenance confirmation is offered while blocked',
        (await page.locator('[data-testid="confirm-provenance"]').count())
        === 0);

  // The ordinary user must not be asked to invent kinetics.
  const routedPanel = await page.locator('.rpk__categories').innerText()
    .catch(() => '');
  check('no rate constant is requested in the routed panel',
        !/Absorption rate constant|Elimination rate constant/i.test(routedPanel));

  // The category is not literally empty: bioavailability F = 1 is shown,
  // because it is true by definition of an intravenous route. What must NOT
  // appear is any fitted parameter, since no reviewed set exists.
  const paramCategory = await page
    .locator('[data-testid="pk-category-parameters"]').innerText();
  const flat = paramCategory.replace(/\s+/g, ' ').slice(0, 140);
  check('no fitted PK parameter is offered',
        !/\bCL\b|\bVc\b|\bQ\b|\bVp\b/.test(paramCategory), flat);
  check('bioavailability is attributed to the route, not to a citation',
        !/From cited parameter set/i.test(paramCategory), flat);

  check('Research Use Only notice is present',
        /Research Use Only/i.test(body));

  await page.screenshot({ path: `${OUT}/pk-02-blocked-plan.png`,
                          fullPage: true });
  log('captured pk-02-blocked-plan', 'ok');

  // The legacy depot fields must be demoted behind a disclosure, not primary.
  const legacy = page.locator('[data-testid="legacy-depot-inputs"]');
  if (await legacy.count()) {
    const open = await legacy.evaluate((el) => el.hasAttribute('open'));
    check('legacy depot inputs are collapsed by default', !open);
  }

  // ------------------------------ run, and inspect the Results page
  // The design score still runs; the PK engine must not be called at all.
  await page.getByRole('button', { name: /Run Simulation/i }).click();
  await page.waitForSelector('[data-testid="result-card"]', { timeout: 20000 });

  const resultsBody = await page.locator('body').innerText();
  check('legacy four-rate-constant message is gone from Results',
        !/The dose and the four first-order rate constants are required/i
          .test(resultsBody));
  check('"Supply the required inputs" is not offered',
        (await page.getByRole('button',
          { name: /Supply the required inputs/i }).count()) === 0);

  const reason = await page.locator('[data-testid="pk-empty-reason"]')
    .innerText();
  check('Results states the replacement message',
        /PK simulation is not yet operational for IV trastuzumab/i.test(reason),
        reason.slice(0, 100));
  check('Results names the missing requirements',
        /Missing requirements include/i.test(reason));
  check('Results states no PK results exist',
        /No simulation has been executed and no PK results exist/i.test(reason));

  check('no half-life or AUC is shown',
        !/half-life|\bAUC\b/i.test(resultsBody));
  check('no PK panel is rendered',
        (await page.locator('[data-testid="pk-panel"]').count()) === 0);

  await page.screenshot({ path: `${OUT}/pk-03-results-blocked.png`,
                          fullPage: true });
  log('captured pk-03-results-blocked', 'ok');

  check('the legacy depot engine was never called',
        !calls.some((u) => u.endsWith('/api/v1/pk/simulate')),
        calls.filter((u) => u.endsWith('/api/v1/pk/simulate')).join('; '));
  check('no failed /api/v1/pk/ request during the walkthrough',
        failedRequests.length === 0, failedRequests.join('; '));

  await browser.close();

  console.log('\n' + '='.repeat(70));
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log('  - ' + p);
  console.log('='.repeat(70));
  process.exit(problems.length ? 1 : 0);
}

main().catch((e) => { console.error('WALKTHROUGH FAILED:', e); process.exit(2); });
