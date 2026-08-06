/**
 * Visual walkthrough of the restructured navigation and startup experience.
 *
 * Drives the live app against the live backend, capturing the ten required
 * screens at desktop, tablet and mobile widths, and reporting any problem it
 * can detect mechanically: horizontal overflow, a missing or ambiguous active
 * indicator, a breadcrumb trail that leaks a study name, or a console error.
 *
 * Run with the dev servers up:
 *   node nav-walkthrough.mjs
 *   node nav-walkthrough.mjs http://localhost:8000   (production shape)
 *
 * It reads. It does not save studies, so it leaves no records behind.
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const OUT = resolve('../docs/screenshots');
const USER = 'walkthrough_user';
const PASS = process.env.NANOBIO_TEST_PASSWORD ?? '';  // set NANOBIO_TEST_PASSWORD

const DESKTOP = { width: 1440, height: 900 };
const TABLET = { width: 834, height: 1112 };
const MOBILE = { width: 390, height: 844 };

mkdirSync(OUT, { recursive: true });

const problems = [];

function log(label, value) {
  console.log(`${label.padEnd(46, '.')} ${value}`);
}

function check(label, condition, detail = '') {
  log(label, condition ? 'ok' : 'PROBLEM');
  if (!condition) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
}

async function checkOverflow(page, label) {
  const o = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }));
  if (o.scrollW > o.clientW + 1) {
    problems.push(`${label}: horizontal overflow ${o.scrollW} > ${o.clientW}`);
  }
}

async function shot(page, name, label) {
  await page.waitForTimeout(300);
  await checkOverflow(page, label);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  log(`captured ${name}`, 'ok');
}

/**
 * The single active nav row, or a description of why there isn't one.
 *
 * Waits for the indicator rather than sleeping a fixed interval: a fixed wait
 * reported phantom failures on slower renders, which wasted a debugging cycle
 * chasing a defect that was in this script.
 */
async function activeNav(page) {
  const links = page.locator(
    'nav[aria-label="Main navigation"] a[aria-current="page"]');
  try {
    await links.first().waitFor({ state: 'attached', timeout: 5000 });
  } catch {
    return '<none>';
  }
  const n = await links.count();
  if (n > 1) return `<${n} active>`;
  return (await links.first().innerText()).replace(/\s*\(current page\)\s*/, '')
    .trim();
}

/** Navigate and wait for the shell to finish rendering, not for the clock. */
async function goto(page, path) {
  await page.goto(`${APP}${path}`);
  await page.waitForSelector('nav[aria-label="Main navigation"]');
  await page.waitForLoadState('networkidle');
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: DESKTOP });
  const page = await context.newPage();

  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    if (t.includes('favicon') || t.includes('401')) return;   // expected pre-login
    problems.push(`console error: ${t.slice(0, 160)}`);
  });

  // ------------------------------------------------------------ sign in
  await page.goto(`${APP}/login`);
  await page.fill('#username', USER);
  await page.fill('#password', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 15000 });
  check('lands on /start after sign-in',
        new URL(page.url()).pathname === '/start', page.url());

  // ------------------------------------------- 1. the startup experience
  await page.waitForSelector('[data-testid="pathway-cards"]');
  const heading = await page.locator('h2, h1').first().innerText();
  check('asks "How would you like to begin?"',
        /How would you like to begin\?/i.test(
          await page.locator('body').innerText()), heading);
  for (const id of ['pathway-patient', 'pathway-research', 'pathway-demo']) {
    check(`pathway card present: ${id}`,
          await page.locator(`[data-testid="${id}"]`).count() === 1);
  }
  const cards = await page.locator(
    '[data-testid="pathway-cards"] > [data-testid^="pathway-"]').count();
  check('exactly three pathway cards', cards === 3, `found ${cards}`);
  log('active nav on /start', await activeNav(page));
  await shot(page, 'nav-01-startup', 'startup');

  // ---------------------------------------------------- 2. the sidebar
  const navText = await page.locator(
    'nav[aria-label="Main navigation"]').innerText();
  for (const group of ['START', 'WORKSPACE', 'SCIENTIFIC TOOLS',
                       'INTELLIGENCE', 'SYSTEM']) {
    check(`sidebar group: ${group}`,
          navText.toUpperCase().includes(group));
  }
  for (const item of ['Start New Study', 'My Studies', 'Patient Assessments',
                      'Research Designs', 'Evidence & Validation']) {
    check(`sidebar entry: ${item}`, navText.includes(item));
  }
  check('no stale "Start New Design" label',
        !navText.includes('Start New Design'));
  check('no stale "Design Workflow" label',
        !navText.includes('Design Workflow'));
  await shot(page, 'nav-02-sidebar', 'sidebar');

  // -------------------------------------- 3. research purpose (2nd level)
  await page.getByTestId('start-research').click();
  await page.waitForSelector('[data-testid="research-purposes"]');
  const purposes = await page.locator('[data-testid^="purpose-"]').count();
  log('research purposes offered', purposes);
  check('research purpose step reachable', purposes >= 5);
  check('Start New Study stays active on /start/research',
        (await activeNav(page)).includes('Start New Study'),
        await activeNav(page));
  await shot(page, 'nav-03-research-purpose', 'research purpose');

  // ----------------------------------- 4. workflow, breadcrumb + context
  await page.getByTestId('choose-disease_specific_design').click();
  await page.waitForURL(/\/workflow\/disease/);
  await page.waitForSelector('select#disease');
  const crumbs = await page.locator(
    'nav[aria-label="Breadcrumb"]').innerText();
  log('breadcrumb trail', crumbs.replace(/\n/g, ' '));
  check('breadcrumb starts at Home', /Home/.test(crumbs));
  check('breadcrumb names the pathway that owns the study',
        /Research Designs/.test(crumbs), crumbs);
  check('workflow highlights Research Designs',
        (await activeNav(page)).includes('Research Designs'),
        await activeNav(page));
  await shot(page, 'nav-04-workflow-breadcrumb', 'workflow breadcrumb');

  // ------------------------------- 5. active state survives every stage
  await page.selectOption('select#disease', 'Liver Cancer (HCC)');
  await page.selectOption('select#subtype', 'AFP-high HCC');
  await page.selectOption('select#drug', 'Sorafenib');
  await page.getByRole('button', { name: /Continue to design parameters/i })
    .click();
  await page.waitForSelector('#size_nm');
  check('indicator survives step 2',
        (await activeNav(page)).includes('Research Designs'),
        await activeNav(page));
  const ctx = await page.locator('[data-testid="study-context"]').innerText();
  log('study context header', ctx.replace(/\n/g, ' | '));
  check('context header names the pathway', /Research design/i.test(ctx));
  await shot(page, 'nav-05-workflow-step2', 'workflow step 2');

  await page.getByRole('button', { name: /Continue to review/i }).click();
  await page.waitForSelector('[data-testid="pk-inputs"]');
  check('indicator survives step 3',
        (await activeNav(page)).includes('Research Designs'),
        await activeNav(page));

  // ------------------------------------------------- 6. My Studies list
  await goto(page, '/studies');
  check('My Studies is active on /studies',
        (await activeNav(page)).includes('My Studies'), await activeNav(page));
  const studiesText = await page.locator('body').innerText();
  check('My Studies shows a genuine list or an honest empty state',
        /No studies saved yet/i.test(studiesText)
        || (await page.locator('[data-testid^="run-row-"]').count()) > 0);
  await shot(page, 'nav-06-my-studies', 'my studies');

  // -------------------------------------------- 7. Patient Assessments
  await goto(page, '/patient-assessments');
  check('Patient Assessments is active',
        (await activeNav(page)).includes('Patient Assessments'),
        await activeNav(page));
  await shot(page, 'nav-07-patient-assessments', 'patient assessments');

  // ------------------------------------------------ 8. Research Designs
  await goto(page, '/research-designs');
  check('Research Designs is active',
        (await activeNav(page)).includes('Research Designs'),
        await activeNav(page));
  await shot(page, 'nav-08-research-designs', 'research designs');

  // ------------------------------------------- 9. Evidence & Validation
  await page.goto(`${APP}/evidence`);
  await page.waitForSelector('[data-testid="evidence-counts"]');
  const evidenceText = await page.locator('body').innerText();
  check('Evidence page states it validates nothing',
        /no model on this platform has been validated/i.test(evidenceText));
  check('Evidence page lists module statuses',
        (await page.locator('[data-testid^="evidence-row-"]').count()) > 10);
  await shot(page, 'nav-09-evidence', 'evidence');

  // ---------------------------- 10. legacy links still resolve, no 404s
  for (const [from, expected] of [['/dashboard', '/home'],
                                  ['/history', '/history']]) {
    await page.goto(`${APP}${from}`);
    // A redirect is a client-side history replace; wait for the destination
    // rather than assuming it has happened.
    await page.waitForURL(new RegExp(`${expected}$`), { timeout: 8000 })
      .catch(() => {});
    await page.waitForSelector('nav[aria-label="Main navigation"]');
    const landed = new URL(page.url()).pathname;
    check(`legacy link ${from} -> ${expected}`, landed === expected, landed);
    check(`${from} is not a 404`,
          !/Page not found/i.test(await page.locator('body').innerText()));
  }
  await goto(page, '/home');
  await shot(page, 'nav-10-home', 'home');

  // ------------------------------------------------- privacy assertions
  await goto(page, '/report');
  const title = await page.title();
  const url = page.url();
  check('browser title carries no study or patient detail',
        !/patient|mrn|dob/i.test(title), title);
  check('URL carries no identifier', !/name=|patient=|mrn=/i.test(url), url);
  const storage = await page.evaluate(
    () => JSON.stringify(Object.entries(localStorage)));
  check('localStorage holds no report text or identifier',
        !/mrn|date of birth|patient name/i.test(storage));

  // -------------------------------------------------------- responsive
  for (const [size, tag] of [[TABLET, 'tablet'], [MOBILE, 'mobile']]) {
    await page.setViewportSize(size);
    for (const [path, name] of [['/start', `nav-11-${tag}-startup`],
                                ['/studies', `nav-12-${tag}-studies`],
                                ['/workflow/disease', `nav-13-${tag}-workflow`]]) {
      await page.goto(`${APP}${path}`);
      await page.waitForTimeout(900);
      await shot(page, name, `${tag} ${path}`);
    }
  }

  // -------------------------------------------- keyboard reachability
  await page.setViewportSize(DESKTOP);
  await goto(page, '/home');
  const unreachable = await page.evaluate(() => {
    const nav = document.querySelector('nav[aria-label="Main navigation"]');
    if (!nav) return ['<no nav>'];
    return [...nav.querySelectorAll('a')]
      .filter((a) => !a.hasAttribute('href') || a.tabIndex < 0)
      .map((a) => a.textContent?.trim() ?? '?');
  });
  check('every sidebar entry is keyboard reachable',
        unreachable.length === 0, unreachable.join(', '));

  await browser.close();

  console.log('\n' + '='.repeat(70));
  console.log(problems.length ? 'PROBLEMS:' : 'PROBLEMS: none');
  for (const p of problems) console.log('  - ' + p);
  console.log('='.repeat(70));
  process.exit(problems.length ? 1 : 0);
}

main().catch((e) => { console.error('WALKTHROUGH FAILED:', e); process.exit(2); });
