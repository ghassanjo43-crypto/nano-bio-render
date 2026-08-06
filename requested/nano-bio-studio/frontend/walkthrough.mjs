/**
 * Visual walkthrough of the integrated application.
 *
 * Drives the live app against the live backend at desktop and tablet widths,
 * capturing the ten required screenshots and reporting any layout problem it
 * can detect mechanically (horizontal overflow, missing landmarks).
 *
 * Run with the dev servers up:
 *   node walkthrough.mjs
 *
 * It creates a throwaway account, exercises the full demo journey, then leaves
 * the demo runs in place so the screenshots reflect real stored records. Use
 * `demo_data.py reset --confirm` afterwards to clear them.
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

// Origin to drive. The API is same-origin (dev server proxy, or the backend
// serving the built SPA), so only one address is ever needed.
//   node walkthrough.mjs                      -> dev server
//   node walkthrough.mjs http://localhost:8000 -> production shape
const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const OUT = resolve('../docs/screenshots');
const USER = 'walkthrough_user';
const PASS = process.env.NANOBIO_TEST_PASSWORD ?? '';  // set NANOBIO_TEST_PASSWORD

const DESKTOP = { width: 1440, height: 900 };
const TABLET = { width: 834, height: 1112 };

mkdirSync(OUT, { recursive: true });

const problems = [];
const notes = [];

function log(label, value) {
  const line = `${label.padEnd(42, '.')} ${value}`;
  notes.push(line);
  console.log(line);
}

/** Fail loudly on horizontal overflow — it is the most common layout defect. */
async function checkOverflow(page, label) {
  const overflow = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }));
  if (overflow.scrollW > overflow.clientW + 1) {
    problems.push(
      `${label}: horizontal overflow ${overflow.scrollW}px > ${overflow.clientW}px`);
  }
}

async function shot(page, name, label) {
  await page.waitForTimeout(350);
  await checkOverflow(page, label);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  log(`captured ${name}`, 'ok');
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: DESKTOP });
  const page = await context.newPage();

  page.on('pageerror', (e) => problems.push(`console pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const text = m.text();
    // Expected, not a defect: the shell probes `/auth/me` on load, which is a
    // 401 until the user signs in. Anything else is reported.
    if (text.includes('favicon') || text.includes('401')) return;
    problems.push(`console error: ${text.slice(0, 160)}`);
  });

  // ------------------------------------------------- login through the UI
  // Deliberately NOT pre-authenticating over the API: `page.request` shares the
  // context cookie jar, so a prior API login would redirect /login to /start
  // and the form would never render.
  await page.goto(`${APP}/login`);
  await page.fill('#username', USER);
  await page.fill('#password', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 15000 });
  log('logged in, landed on', new URL(page.url()).pathname);

  // ------------------------------------------------- 1. demo workspace
  await page.goto(`${APP}/demo`);
  await page.waitForSelector('[data-testid="scenario-cards"]');
  const cardCount = await page.locator('[data-testid^="scenario-"]').count();
  log('demo scenario cards', cardCount);
  await shot(page, 'int-01-demo-workspace', 'demo workspace');

  // ------------------------------------------------- 2. scenario preview
  await page.locator('[data-testid="scenario-liver-hcc-galnac"]')
    .getByRole('button', { name: /Preview/i }).click();
  await page.waitForSelector('[data-testid="scenario-preview"]');
  const previewText = await page.locator('[data-testid="scenario-preview"]').innerText();
  log('preview states not-patient-data', /not patient data/i.test(previewText));
  await shot(page, 'int-02-scenario-preview', 'scenario preview');

  // ------------------------------------------------- 3. loaded step 1
  await page.getByTestId('confirm-load').click();
  await page.waitForURL(/\/workflow\/disease/);
  await page.waitForSelector('select#disease');
  log('step 1 indication', await page.locator('select#disease').inputValue());
  log('step 1 drug', await page.locator('select#drug').inputValue());
  await shot(page, 'int-03-loaded-step1', 'loaded step 1');

  // ------------------------------------------------- 4. populated step 2
  await page.getByRole('button', { name: /Continue to design parameters/i }).click();
  await page.waitForSelector('#size_nm');
  log('step 2 size_nm', await page.locator('#size_nm').inputValue());
  log('step 2 charge_mv', await page.locator('#charge_mv').inputValue());
  await shot(page, 'int-04-loaded-step2', 'populated step 2');

  // ------------------------------------------------- 5. PK review
  await page.getByRole('button', { name: /Continue to review/i }).click();
  await page.waitForSelector('[data-testid="pk-inputs"]');
  // The depot rate constants are only offered for a route that genuinely
  // has an absorption phase. A demo scenario supplies k_abs, so it is a
  // depot study; select the compatible route as a user would.
  await page.waitForFunction(() => {
    const sel = document.querySelector('select#pk-route');
    return sel instanceof HTMLSelectElement && sel.options.length > 1;
  }, { timeout: 10000 });
  await page.selectOption('select#pk-route', 'subcutaneous');
  await page.waitForSelector('[data-testid="legacy-depot-inputs"]');
  log('step 3 k_el', await page.locator('#pk-kel_per_h').inputValue());
  const runStatus = await page.getByTestId('pk-run-status').innerText();
  log('PK will run', /will run on the inputs above/i.test(runStatus));
  await shot(page, 'int-05-pk-review', 'PK review');

  // ------------------------------------------------- 6. calculated results
  await page.getByRole('button', { name: /Run Simulation/i }).click();
  await page.waitForSelector('[data-testid="pk-panel"]', { timeout: 20000 });
  const delivery = await page.locator('.sv-gauge__number').first().innerText();
  log('delivery score (calculated)', delivery);
  log('PK C_max (calculated)', await page.getByTestId('pk-cmax').innerText());
  log('clearance shown as', await page.getByTestId('pk-clearance').innerText());
  await shot(page, 'int-06-calculated-results', 'calculated results');

  // save the run
  await page.getByTestId('save-run').click();
  await page.waitForSelector('[data-testid="run-saved"]');
  log('run saved', (await page.getByTestId('run-saved').innerText()).slice(0, 60));

  // ------------- second scenario, so comparison has two genuine runs
  await page.goto(`${APP}/demo`);
  await page.waitForSelector('[data-testid="scenario-cards"]');
  await page.locator('[data-testid="scenario-breast-her2-targeted"]')
    .getByRole('button', { name: /Load scenario/i }).click();
  await page.waitForSelector('[data-testid="scenario-preview"]');
  await page.getByTestId('confirm-load').click();
  await page.waitForURL(/\/workflow\/disease/);
  await page.getByRole('button', { name: /Continue to design parameters/i }).click();
  await page.getByRole('button', { name: /Continue to review/i }).click();
  await page.waitForSelector('[data-testid="pk-inputs"]');
  // The depot rate constants are only offered for a route that genuinely
  // has an absorption phase. A demo scenario supplies k_abs, so it is a
  // depot study; select the compatible route as a user would.
  await page.waitForFunction(() => {
    const sel = document.querySelector('select#pk-route');
    return sel instanceof HTMLSelectElement && sel.options.length > 1;
  }, { timeout: 10000 });
  await page.selectOption('select#pk-route', 'subcutaneous');
  await page.waitForSelector('[data-testid="legacy-depot-inputs"]');
  await page.getByRole('button', { name: /Run Simulation/i }).click();
  await page.waitForSelector('[data-testid="pk-panel"]', { timeout: 20000 });
  await page.getByTestId('save-run').click();
  await page.waitForSelector('[data-testid="run-saved"]');
  log('second run saved', 'ok');

  // ------------------------------------------------- 8. simulation history
  //
  // NOTE ON STATE: this script saves two runs every time it executes, and does
  // not clean up after itself. Left to accumulate over many runs the history
  // grows unbounded and the comparison step below becomes unreliable. Clear it
  // first with:
  //     python nanobio_studio_backend\scripts\demo_data.py reset --confirm
  await page.goto(`${APP}/history`);
  await page.waitForSelector('[data-testid^="run-row-"]');
  const rows = await page.locator('[data-testid^="run-row-"]').count();
  log('history rows', rows);
  if (rows > 8) {
    problems.push(
      `history has ${rows} accumulated runs; run `
      + '`demo_data.py reset --confirm` before this walkthrough');
  }
  await shot(page, 'int-08-simulation-history', 'simulation history');

  // ------------------------------------------------- 7. compare designs
  const boxes = page.locator('[data-testid^="run-row-"] input[type="checkbox"]');
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByTestId('compare-selected').click();
  await page.waitForSelector('[data-testid="compare-notice"]');
  const compareText = await page.locator('body').innerText();
  log('compare states no ranking', /No overall ranking is produced/i.test(compareText));
  await shot(page, 'int-07-compare-designs', 'compare designs');

  // ------------------------------------------------- 9. generated report
  await page.goto(`${APP}/history`);
  await page.waitForSelector('[data-testid^="run-row-"]');
  await page.locator('[data-testid^="run-row-"]').first()
    .getByRole('button', { name: /^Open$/ }).click();
  await page.waitForSelector('[data-testid="download-report"]');
  const download = page.waitForEvent('download');
  await page.getByTestId('download-report').click();
  const file = await download;
  const path = `${OUT}/../reports/${file.suggestedFilename()}`;
  mkdirSync(resolve(OUT, '../reports'), { recursive: true });
  await file.saveAs(path);
  log('report downloaded', file.suggestedFilename());
  await shot(page, 'int-09-generated-report', 'stored run + report');

  // ------------------------------------------------ 10. unavailable module
  await page.goto(`${APP}/ai-co-designer`);
  await page.waitForTimeout(500);
  const aiText = await page.locator('body').innerText();
  log('AI module shows honest status',
      /Not yet operational/i.test(aiText));
  log('AI module shows no number', !/\d+\.\d{2}/.test(
    aiText.replace(/[\d.]+ ?kB/g, '')));
  await shot(page, 'int-10-unavailable-module', 'unavailable module');

  // ---------------------------------------------------------- tablet
  await page.setViewportSize(TABLET);
  for (const [path, name] of [
    ['/demo', 'int-11-tablet-demo'],
    ['/history', 'int-12-tablet-history'],
    ['/compare', 'int-13-tablet-compare'],
  ]) {
    await page.goto(`${APP}${path}`);
    await page.waitForTimeout(900);
    await shot(page, name, `tablet ${path}`);
  }

  await browser.close();

  console.log('\n' + '='.repeat(70));
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log('  - ' + p);
  console.log('='.repeat(70));
  process.exit(problems.length ? 1 : 0);
}

main().catch((e) => { console.error('WALKTHROUGH FAILED:', e); process.exit(2); });
