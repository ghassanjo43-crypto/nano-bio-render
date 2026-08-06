/**
 * Browser walkthrough of the detail levels and molecular population panel.
 *
 * Verification cases from the specification:
 *   A. 100 nm / -5 mV / 85%, all structure unspecified;
 *   B. liposome with lipid constants supplied;
 *   C. PEGylated targeted nanoparticle;
 *   D. mesoporous silica.
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const APP = process.argv[2] ?? 'http://127.0.0.1:8100';
const OUT = resolve('../docs/screenshots');
const USER = 'walkthrough_user';
const PASS = process.env.NANOBIO_TEST_PASSWORD ?? '';  // set NANOBIO_TEST_PASSWORD

mkdirSync(OUT, { recursive: true });

const problems = [];
const log = (l, v) => console.log(`${l.padEnd(52, '.')} ${v}`);
function check(l, ok, detail = '') {
  log(l, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${l}${detail ? `: ${detail}` : ''}`);
}

async function openSurfaceTab(page) {
  const tab = page.getByRole('tab', { name: /Surface characteristics/i });
  if (await tab.count()) await tab.first().click();
  await page.waitForSelector('#coating_thickness_nm', { timeout: 15000 });
}

async function openTargetingTab(page) {
  const tab = page.getByRole('tab', { name: /Targeting configuration/i });
  if (await tab.count()) await tab.first().click();
  await page.waitForSelector('#ligand_density_percent', { timeout: 15000 });
}

async function backToDesign(page) {
  await page.getByRole('button', { name: /Back to design parameters/i })
    .first().click();
  await page.waitForSelector('#size_nm', { timeout: 15000 });
}

async function main() {
  const browser = await chromium.launch({
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
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

  /* ------------------------------------------------ case A: minimal ---- */
  await page.goto(`${APP}/workflow/disease`);
  await page.waitForSelector('select#disease');
  await page.selectOption('select#disease', 'Breast Cancer');
  await page.selectOption('select#subtype', 'HER2-enriched (ER-, PR-, HER2+)');
  await page.selectOption('select#drug', 'Trastuzumab (Herceptin)');
  await page.getByRole('button', { name: /Continue to design parameters/i })
    .click();
  await page.waitForSelector('#size_nm');
  await page.fill('#size_nm', '100');
  await page.fill('#charge_mv', '-5');
  await page.fill('#encapsulation_percent', '85');
  log('case A design', '100 nm, -5 mV, 85%, structure unspecified');

  await page.getByTestId('view-in-3d-step2').click();
  await page.waitForSelector('[data-testid="particle-canvas"]',
                             { timeout: 25000 });
  await page.waitForTimeout(2500);
  const viewport = page.locator('[data-testid="builder-viewport"]');

  check('population panel present',
        (await page.locator('[data-testid="population-panel"]').count()) === 1);
  check('scientific legend present',
        (await page.locator('[data-testid="scientific-legend"]').count()) === 1);

  const payloadPop = await page
    .locator('[data-testid="population-payload_molecules"]').innerText();
  check('payload population reported as not calculable',
        /Cannot calculate from current inputs/i.test(payloadPop));
  check('rendered count still shown',
        /Rendered representative objects/i.test(payloadPop));
  check('ratio reported unknown', /Unknown/i.test(payloadPop));

  await viewport.screenshot({ path: `${OUT}/mol-01-overview.png` });
  log('captured mol-01-overview', 'ok');
  await page.locator('[data-testid="population-panel"]')
    .screenshot({ path: `${OUT}/mol-02-population-panel.png` });
  log('captured mol-02-population-panel', 'ok');

  /* --------------------------------------------- detail levels --------- */
  await page.selectOption('select#np3d-detail', 'structural');
  await page.getByTestId('mode-cutaway').click();
  await page.waitForTimeout(2000);
  await viewport.screenshot({ path: `${OUT}/mol-03-structural-cutaway.png` });
  log('captured mol-03-structural-cutaway', 'ok');

  await page.selectOption('select#np3d-detail', 'molecular');
  await page.getByTestId('mode-whole').click();
  await page.waitForTimeout(2500);
  await viewport.screenshot({ path: `${OUT}/mol-04-molecular-closeup.png` });
  log('captured mol-04-molecular-closeup', 'ok');
  check('molecular patch limitation stated',
        (await page.locator('[data-testid="molecular-patch-note"]').count()) === 1);

  /* ------------------------------------------- quality presets --------- */
  await page.selectOption('select#np3d-quality', 'low');
  await page.waitForTimeout(1600);
  await viewport.screenshot({ path: `${OUT}/mol-05-quality-low.png` });
  await page.selectOption('select#np3d-quality', 'high');
  await page.waitForTimeout(2000);
  await viewport.screenshot({ path: `${OUT}/mol-06-quality-high.png` });
  log('captured low / high quality modes', 'ok');
  await page.selectOption('select#np3d-quality', 'balanced');

  /* --------------------------------------- case B: liposome + lipids --- */
  await page.selectOption('select#np-architecture', 'liposome');
  await page.selectOption('select#np-payload-location', 'hydrophilic_core');
  await page.waitForTimeout(1500);

  await page.locator('[data-testid="molecular-assumptions"] summary').click();
  await page.fill('[data-testid="assumption-areaPerLipidNm2"]', '0.65');
  await page.fill('[data-testid="assumption-bilayerThicknessNm"]', '4');
  await page.waitForTimeout(1200);

  const lipidPop = await page.locator('[data-testid="population-lipids"]')
    .innerText();
  check('lipid population calculated once constants supplied',
        /thousand|million/i.test(lipidPop), lipidPop.slice(0, 110));
  check('lipid estimate labelled researcher-supplied',
        /Researcher-supplied inputs/i.test(lipidPop));
  check('lipid estimate separates rendered from physical',
        /Rendered representative objects/i.test(lipidPop));
  check('representation ratio stated',
        /1 rendered object/i.test(lipidPop), lipidPop.slice(0, 110));

  await page.selectOption('select#np3d-detail', 'molecular');
  await page.waitForTimeout(2500);
  await viewport.screenshot({ path: `${OUT}/mol-07-liposome-bilayer.png` });
  log('captured mol-07-liposome-bilayer', 'ok');
  await page.locator('[data-testid="population-lipids"]')
    .screenshot({ path: `${OUT}/mol-08-lipid-population.png` });
  log('captured mol-08-lipid-population', 'ok');

  /* ------------------------------- case C: PEGylated targeted particle -- */
  await backToDesign(page);
  await openSurfaceTab(page);
  await page.fill('#coating_thickness_nm', '8');
  const peg = page.getByRole('button', { name: /PEG \(Stealth\)/i }).first();
  if (await peg.count()) await peg.click();
  await openTargetingTab(page);
  await page.fill('#ligand_density_percent', '40');
  await page.getByTestId('view-in-3d-step2').click();
  await page.waitForSelector('[data-testid="particle-canvas"]',
                             { timeout: 25000 });
  await page.selectOption('select#np-architecture', 'polymeric');
  await page.selectOption('select#np3d-detail', 'molecular');
  await page.waitForTimeout(2800);

  const ligandPop = await page.locator('[data-testid="population-ligands"]')
    .innerText();
  check('percentage ligand density is refused as ambiguous',
        /ambiguous/i.test(ligandPop), ligandPop.slice(0, 130));
  check('the four possible meanings are named',
        /surface coverage/i.test(ligandPop) && /molar percent/i.test(ligandPop)
        && /mass percent/i.test(ligandPop));

  await page.locator('[data-testid="builder-viewport"]')
    .screenshot({ path: `${OUT}/mol-09-peg-ligand-surface.png` });
  log('captured mol-09-peg-ligand-surface', 'ok');

  // Supply the definition and a footprint, then it should calculate.
  await page.locator('[data-testid="molecular-assumptions"] summary').click();
  await page.selectOption('[data-testid="assumption-ligandDensityDefinition"]',
                          'surface_coverage_fraction');
  await page.fill('[data-testid="assumption-molecularFootprintNm2"]', '0.5');
  await page.waitForTimeout(1200);
  const ligandPop2 = await page.locator('[data-testid="population-ligands"]')
    .innerText();
  check('ligand population calculates once the definition is recorded',
        !/Cannot calculate/i.test(ligandPop2), ligandPop2.slice(0, 130));

  /* --------------------------------------- case D: mesoporous silica --- */
  await page.selectOption('select#np-architecture', 'silica');
  await page.waitForTimeout(1500);
  const porePop = await page
    .locator('[data-testid="population-pore_bound_molecules"]').innerText();
  check('pore loading refused when porosity is not recorded',
        /Cannot calculate|Porosity is not recorded/i.test(porePop),
        porePop.slice(0, 120));

  await page.fill('[data-testid="assumption-poreVolumeNm3"]', '20000');
  await page.fill('[data-testid="assumption-payloadMolecularVolumeNm3"]', '0.5');
  await page.waitForTimeout(1200);
  const porePop2 = await page
    .locator('[data-testid="population-pore_bound_molecules"]').innerText();
  check('pore capacity calculated once porosity is supplied',
        /thousand|million|\d{3,}/.test(porePop2), porePop2.slice(0, 120));
  check('pore result labelled as a capacity bound',
        /capacity bound/i.test(porePop2));

  await page.locator('[data-testid="builder-viewport"]')
    .screenshot({ path: `${OUT}/mol-10-silica.png` });
  log('captured mol-10-silica', 'ok');

  /* ---------------------------------------------- final assertions ----- */
  const body = await page.locator('body').innerText();
  check('one-to-one disclaimer present',
        /do not necessarily correspond one-to-one/i.test(body));
  check('no atomic structure is claimed',
        !/atomic structure of/i.test(body));

  await browser.close();
  console.log('\n' + '='.repeat(70));
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log('  - ' + p);
  console.log('='.repeat(70));
  process.exit(problems.length ? 1 : 0);
}

main().catch((e) => { console.error('WALKTHROUGH FAILED:', e); process.exit(2); });
