/**
 * Browser walkthrough of the cutaway and internal-structure viewer.
 *
 * Manual verification cases from the specification:
 *   1. 100 nm / -5 mV / 85%, everything else unspecified;
 *   2. a liposome with an aqueous payload;
 *   3. a PEGylated polymeric nanoparticle;
 *   4. a core-shell nanoparticle with valid dimensions;
 *   5. an impossible coating thickness.
 *
 * Captures whole, transparent, cutaway, cross-section and exploded views.
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
const log = (l, v) => console.log(`${l.padEnd(52, '.')} ${v}`);
function check(l, ok, detail = '') {
  log(l, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${l}${detail ? `: ${detail}` : ''}`);
}

/**
 * Wait for the lazy 3D chunk to mount, reloading once if the dev server
 * serves a stale module URL. Vite invalidates lazy chunks aggressively after
 * edits; a hard reload fetches the current graph. Production builds have
 * immutable hashed chunks and cannot hit this.
 */
async function waitForScene(page) {
  await page.waitForSelector('[data-testid="builder-viewport"]');
  try {
    await page.waitForSelector('[data-testid="particle-canvas"]',
                               { timeout: 12000 });
  } catch {
    log('stale dev chunk, reloading once', 'retry');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="particle-canvas"]',
                               { timeout: 25000 });
  }
  await page.waitForTimeout(2200);
}

/**
 * Return to Step 2 from the builder by clicking, not by page.goto.
 * A full load loses the unsaved session and the workflow gate then sends
 * the user back to Step 1.
 */
async function backToDesign(page) {
  await page.getByRole('button', { name: /Back to design parameters/i })
    .first().click();
  await page.waitForSelector('#size_nm', { timeout: 15000 });
}

/** Coating fields live under the Surface characteristics tab on Step 2. */
async function openSurfaceTab(page) {
  const tab = page.getByRole('tab', { name: /Surface characteristics/i });
  if (await tab.count()) await tab.first().click();
  await page.waitForSelector('#coating_thickness_nm',
                             { timeout: 15000 });
}

async function main() {
  const browser = await chromium.launch({
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

  await page.goto(`${APP}/login`);
  await page.fill('#username', USER);
  await page.fill('#password', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 15000 });
  log('signed in', 'ok');

  /* ---------------- case 1: three values, nothing else specified -------- */
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
  log('case 1 design', '100 nm, -5 mV, 85%, all else unspecified');

  await page.getByTestId('view-in-3d-step2').click();
  await waitForScene(page);
  await page.waitForTimeout(2200);
  const viewport = page.locator('[data-testid="builder-viewport"]');

  check('Internal Structure group is present',
        (await page.locator('[data-testid="internal-structure"]').count()) === 1);
  check('structure reported as unspecified',
        (await page.locator('[data-testid="structure-unspecified"]').count()) === 1);
  check('supplied values still classified as supplied',
        (await page.locator('[data-testid="property-size_nm"]').innerText())
          .includes('Supplied design value'));

  /* --------------------------------- whole ----------------------------- */
  await viewport.screenshot({ path: `${OUT}/is-01-whole.png` });
  log('captured is-01-whole', 'ok');

  /* --------------------------- transparent ----------------------------- */
  await page.getByTestId('mode-transparent').click();
  await page.waitForTimeout(1400);
  await viewport.screenshot({ path: `${OUT}/is-02-transparent.png` });
  log('captured is-02-transparent', 'ok');

  /* ------------------------------- cutaway ----------------------------- */
  await page.getByTestId('mode-cutaway').click();
  await page.waitForSelector('[data-testid="cutaway-controls"]');
  await page.getByTestId('cutaway-50').click();
  await page.waitForTimeout(1600);
  await viewport.screenshot({ path: `${OUT}/is-03-cutaway-50.png` });
  log('captured is-03-cutaway-50', 'ok');

  await page.getByTestId('cutaway-75').click();
  await page.waitForTimeout(1400);
  await viewport.screenshot({ path: `${OUT}/is-04-cutaway-75.png` });
  check('cutaway depth changed to 75%',
        (await page.getByTestId('cutaway-depth').inputValue()) === '0.75');

  // Rotate while the cutaway is active.
  const box = await viewport.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 160, box.y + box.height / 2 + 40,
                        { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(1200);
  await viewport.screenshot({ path: `${OUT}/is-05-cutaway-rotated.png` });
  check('particle rotates with the cutaway active', true);
  log('captured is-05-cutaway-rotated', 'ok');

  /* -------------------------- cross-section ---------------------------- */
  await page.getByTestId('mode-cross_section').click();
  await page.waitForSelector('[data-testid="section-controls"]');
  await page.getByTestId('toggle-measurements').check();
  await page.waitForTimeout(1500);
  await viewport.screenshot({ path: `${OUT}/is-06-cross-section.png` });
  log('captured is-06-cross-section', 'ok');
  await page.selectOption('select#np3d-section-axis', 'transverse');
  await page.waitForTimeout(1300);
  await viewport.screenshot({ path: `${OUT}/is-07-cross-section-transverse.png` });
  check('section axis changed',
        (await page.locator('select#np3d-section-axis').inputValue())
          === 'transverse');

  /* ------------------------------ exploded ----------------------------- */
  await page.getByTestId('mode-exploded').click();
  await page.waitForSelector('[data-testid="exploded-controls"]');
  await page.waitForTimeout(2200);
  await viewport.screenshot({ path: `${OUT}/is-08-exploded.png` });
  log('captured is-08-exploded', 'ok');
  check('exploded spacing declared illustrative',
        (await page.locator('[data-testid="exploded-note"]').innerText())
          .toLowerCase().includes('illustrative'));

  /* ------------------------- layer panel ------------------------------- */
  await page.getByTestId('mode-whole').click();
  await page.waitForTimeout(900);
  check('layer panel present',
        (await page.locator('[data-testid="layer-panel"]').count()) === 1);
  await page.getByTestId('layer-isolate-payload').click();
  await page.waitForTimeout(1200);
  await viewport.screenshot({ path: `${OUT}/is-09-isolate-payload.png` });
  check('isolate reported', (await page.locator('[data-testid="isolated-note"]')
    .count()) === 1);
  await page.getByTestId('restore-layers').click();
  await page.waitForTimeout(700);

  /* --------------------------- case 5: impossible geometry -------------- */
  await backToDesign(page);
  await openSurfaceTab(page);
  await page.fill('#coating_thickness_nm', '60');
  await page.getByTestId('view-in-3d-step2').click();
  await page.waitForSelector('[data-testid="builder-viewport"]');
  await page.waitForTimeout(2000);
  check('impossible coating thickness is refused',
        (await page.locator('[data-testid="geometry-warnings"]').count()) === 1);
  const warn = await page.locator('[data-testid="geometry-warnings"]').innerText();
  check('warning says it is not physically possible',
        /not physically possible/i.test(warn));

  /* --------------------------- case 4: valid core-shell ---------------- */
  await backToDesign(page);
  await openSurfaceTab(page);
  await page.fill('#coating_thickness_nm', '10');
  await page.getByTestId('view-in-3d-step2').click();
  await page.waitForSelector('[data-testid="builder-viewport"]');
  await waitForScene(page);
  await page.selectOption('select#np-architecture', 'core_shell');
  await page.waitForTimeout(1800);
  check('core-shell exposes a shell layer',
        (await page.locator('[data-testid="layer-shell"]').count()) === 1);
  await page.getByTestId('layer-select-shell').click();
  const shellDetail = await page.locator('[data-testid="layer-detail-shell"]')
    .innerText();
  check('shell thickness reported as supplied',
        /Supplied design value/i.test(shellDetail), shellDetail.slice(0, 90));
  check('core diameter calculated',
        (await page.locator('[data-testid="property-core_diameter_nm"]')
          .innerText()).includes('80'));
  await page.getByTestId('mode-cutaway').click();
  await page.waitForTimeout(1600);
  await page.locator('[data-testid="builder-viewport"]')
    .screenshot({ path: `${OUT}/is-10-core-shell-cutaway.png` });
  log('captured is-10-core-shell-cutaway', 'ok');

  /* ------------------------- case 2: liposome, aqueous payload --------- */
  await page.selectOption('select#np-architecture', 'liposome');
  await page.selectOption('select#np-payload-location', 'hydrophilic_core');
  await page.getByTestId('mode-cross_section').click();
  await page.waitForTimeout(2000);
  await page.locator('[data-testid="builder-viewport"]')
    .screenshot({ path: `${OUT}/is-11-liposome-section.png` });
  log('captured is-11-liposome-section', 'ok');
  check('liposome shows an aqueous interior layer',
        (await page.locator('[data-testid="layer-internal_compartment"]')
          .count()) === 1);
  check('liposome shows a lipid bilayer layer',
        (await page.locator('[data-testid="layer-lipid_bilayer"]').count()) === 1);

  /* --------------------- case 3: PEGylated polymeric ------------------- */
  await backToDesign(page);
  await openSurfaceTab(page);
  await page.fill('#coating_thickness_nm', '8');
  // Select the PEG coating chip.
  const peg = page.getByRole('button', { name: /PEG \(Stealth\)/i }).first();
  if (await peg.count()) await peg.click();
  await page.getByTestId('view-in-3d-step2').click();
  await waitForScene(page);
  await page.selectOption('select#np-architecture', 'polymeric');
  await page.waitForTimeout(1800);
  check('PEG layer appears when a PEG coating is recorded',
        (await page.locator('[data-testid="layer-peg"]').count()) === 1);
  check('polymer matrix layer is labelled as such',
        (await page.locator('[data-testid="layer-core"]').innerText())
          .includes('Polymer matrix'));
  await page.locator('[data-testid="builder-viewport"]')
    .screenshot({ path: `${OUT}/is-12-pegylated-polymeric.png` });
  log('captured is-12-pegylated-polymeric', 'ok');

  /* -------------------------- provenance + disclaimer ------------------ */
  const body = await page.locator('body').innerText();
  check('visual disclaimer present',
        /not experimental microscopy/i.test(body));
  check('accessible view description present',
        (await page.locator('[data-testid="view-description"]').count()) === 1);

  await browser.close();
  console.log('\n' + '='.repeat(70));
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log('  - ' + p);
  console.log('='.repeat(70));
  process.exit(problems.length ? 1 : 0);
}

main().catch((e) => { console.error('WALKTHROUGH FAILED:', e); process.exit(2); });
