/**
 * Browser walkthrough of the Nanoparticle 3D Builder.
 *
 * Manual verification case from the specification:
 *   particle size 100 nm, surface charge −5 mV, encapsulation efficiency 85%,
 *   every other structural property unspecified.
 *
 * Expected: a polished interactive particle renders, and every unspecified
 * structural detail is visibly labelled an illustrative assumption.
 *
 * Captures the normal, transparent-shell-off and cutaway views.
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
const log = (label, value) =>
  console.log(`${label.padEnd(50, '.')} ${value}`);

function check(label, ok, detail = '') {
  log(label, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
}

async function main() {
  const browser = await chromium.launch({
    // Headless Chromium needs a GL backend for WebGL to initialise.
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });

  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    if (t.includes('favicon') || t.includes('401')) return;
    problems.push(`console error: ${t.slice(0, 140)}`);
  });

  const chunkRequests = [];
  page.on('request', (r) => {
    if (/ParticleScene|three/i.test(r.url())) chunkRequests.push(r.url());
  });

  // ------------------------------------------------------------- sign in
  await page.goto(`${APP}/login`);
  await page.fill('#username', USER);
  await page.fill('#password', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 15000 });
  log('signed in', 'ok');

  // ---------------------------------------- lazy loading: not yet fetched
  await page.goto(`${APP}/home`);
  await page.waitForSelector('nav[aria-label="Main navigation"]');
  check('3D module is NOT loaded on an ordinary page',
        chunkRequests.length === 0, chunkRequests.join('; '));

  // ------------------------------------------------- enter the design
  await page.goto(`${APP}/workflow/disease`);
  await page.waitForSelector('select#disease');
  await page.selectOption('select#disease', 'Breast Cancer');
  await page.selectOption('select#subtype', 'HER2-enriched (ER-, PR-, HER2+)');
  await page.selectOption('select#drug', 'Trastuzumab (Herceptin)');
  await page.getByTestId('pathway-continue').click();

  await page.waitForSelector('#size_nm');
  await page.fill('#size_nm', '100');
  await page.fill('#charge_mv', '-5');
  await page.fill('#encapsulation_percent', '85');
  // Every other structural property is left unspecified, as specified.
  log('design entered', '100 nm, -5 mV, 85%; all else unspecified');

  await page.getByTestId('pathway-continue').click();
  await page.getByTestId('pathway-continue').click();
  await page.waitForSelector('[data-testid="pk-inputs"]');

  // ------------------------------------------------------- open the builder
  await page.getByTestId('view-in-3d').click();
  await page.waitForSelector('[data-testid="builder-viewport"]');
  check('builder opened from Step 3', page.url().includes('/builder'));

  const fallback = await page.locator('[data-testid="webgl-unavailable"]')
    .count();
  if (fallback > 0) {
    check('WebGL initialised in the test browser', false,
          'fallback shown — screenshots will not contain a rendered particle');
  } else {
    await page.waitForSelector('[data-testid="particle-canvas"]',
                               { timeout: 20000 });
    check('WebGL canvas rendered', true);
    check('3D module WAS loaded on demand', chunkRequests.length > 0);
  }

  // Give the renderer time to draw a few frames and the shadows to accumulate.
  await page.waitForTimeout(2500);

  // --------------------------------------------------- provenance assertions
  const body = await page.locator('body').innerText();
  check('visual disclaimer is shown',
        /geometry and molecular population may be simplified/i.test(body));
  check('disclaimer denies microscopy',
        /not experimental microscopy/i.test(body));

  const table = await page.locator('[data-testid="property-table"]').innerText();
  check('particle size shown as supplied', /Particle size\s*100 nm/i.test(
    table.replace(/\n/g, ' ')));
  check('surface charge shown as supplied',
        /-5 mV/.test(table));
  check('encapsulation efficiency shown as supplied',
        /85 %/.test(table));

  const missing = await page.locator('[data-testid="missing-list"]').innerText();
  for (const property of ['Particle architecture', 'Core material', 'Shape',
                          'Surface coating', 'Targeting ligand']) {
    check(`unrecorded property named: ${property}`, missing.includes(property));
  }

  const assumptions = await page.locator('[data-testid="assumption-list"]')
    .innerText();
  check('structure labelled not specified',
        /Structure not specified/i.test(assumptions));
  check('payload distribution labelled assumed',
        /illustrative and assumed/i.test(assumptions));

  const legend = await page.locator('[data-testid="provenance-legend"]')
    .innerText();
  for (const label of ['Supplied design value', 'Engine default',
                       'Calculated value', 'Illustrative assumption',
                       'Unavailable information']) {
    check(`legend category: ${label}`, legend.includes(label));
  }

  await page.screenshot({ path: `${OUT}/builder-01-normal.png`,
                          fullPage: true });
  log('captured builder-01-normal', 'ok');

  // Viewport-only crops, so the particle itself is clearly visible.
  const viewport = page.locator('[data-testid="builder-viewport"]');
  await viewport.screenshot({ path: `${OUT}/builder-02-view-normal.png` });
  log('captured builder-02-view-normal', 'ok');

  // ------------------------------------------------------ transparent view
  // Transparency is now an Internal Structure MODE, not a toggle.
  await page.getByTestId('mode-whole').click();
  await page.waitForTimeout(1200);
  await viewport.screenshot({ path: `${OUT}/builder-03-view-opaque.png` });
  await page.getByTestId('mode-transparent').click();
  await page.waitForTimeout(1200);
  await viewport.screenshot({ path: `${OUT}/builder-04-view-transparent.png` });
  log('captured transparent / opaque views', 'ok');

  // ----------------------------------------------------------- cutaway view
  await page.getByTestId('mode-cutaway').click();
  await page.waitForTimeout(1500);
  await viewport.screenshot({ path: `${OUT}/builder-05-view-cutaway.png` });
  log('captured builder-05-view-cutaway', 'ok');
  check('cutaway mode is active',
        (await page.getByTestId('mode-cutaway')
          .getAttribute('aria-checked')) === 'true');
  await page.getByTestId('mode-whole').click();

  // ------------------------------------------------------------ charge field
  await page.getByTestId('layer-visible-charge_field').click();
  await page.waitForSelector('[data-testid="charge-legend"]');
  const chargeNote = await page.locator('[data-testid="charge-current"]')
    .innerText();
  check('charge legend reports the supplied value',
        /-5 mV/.test(chargeNote), chargeNote);
  check('charge bands are described as a display scale',
        /not a classification of colloidal stability/i.test(chargeNote));
  await page.waitForTimeout(900);
  await viewport.screenshot({ path: `${OUT}/builder-06-view-charge.png` });
  log('captured builder-06-view-charge', 'ok');

  // --------------------------------------------------- presets need consent
  await page.getByTestId('preset-gold').click();
  await page.waitForSelector('[data-testid="preset-changes"]');
  const sizeBefore = await page.locator('[data-testid="property-size_nm"]')
    .innerText();
  check('preset dialog lists what it would change',
        (await page.locator('[data-testid="preset-changes"]').innerText())
          .includes('size_nm = 50'));
  check('preset has not changed the design yet',
        sizeBefore.includes('100'));
  await page.getByRole('button', { name: /^Cancel$/ }).click();
  await page.waitForTimeout(400);
  check('cancelling leaves the design untouched',
        (await page.locator('[data-testid="property-size_nm"]').innerText())
          .includes('100'));

  // ------------------------------------------------------ architecture swap
  await page.selectOption('select#np-architecture', 'liposome');
  await page.waitForTimeout(1800);
  await viewport.screenshot({ path: `${OUT}/builder-07-view-liposome.png` });
  log('captured builder-07-view-liposome', 'ok');
  check('supplied size is unchanged after switching architecture',
        (await page.locator('[data-testid="property-size_nm"]').innerText())
          .includes('100'));

  // ------------------------------------------------------------- rendering
  if (fallback === 0) {
    const pixels = await page.evaluate(() => {
      const c = document.querySelector('canvas');
      if (!c) return null;
      return { w: c.width, h: c.height };
    });
    check('canvas has real dimensions',
          Boolean(pixels && pixels.w > 100 && pixels.h > 100),
          JSON.stringify(pixels));
  }

  await browser.close();

  console.log('\n' + '='.repeat(70));
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log('  - ' + p);
  console.log('='.repeat(70));
  process.exit(problems.length ? 1 : 0);
}

main().catch((e) => { console.error('WALKTHROUGH FAILED:', e); process.exit(2); });
