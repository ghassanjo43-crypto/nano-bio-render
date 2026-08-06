/**
 * Persistent-browser smoke test for Candidate Revision and Supersession.
 *
 * This intentionally uses a persistent Chromium profile.  A normal isolated
 * Playwright page cannot catch the failure where authentication or the chosen
 * organization disappears on reload/restart and the version screen silently
 * falls back to another candidate.  The test is read-only: point it at a
 * candidate that already has at least two versions in the development data.
 *
 * PowerShell:
 *   $env:NANOBIO_CANDIDATE_ID = '12'
 *   $env:NANOBIO_WALKTHROUGH_USER = 'researcher'
 *   $env:NANOBIO_WALKTHROUGH_PASSWORD = '<password>'
 *   node candidate-version-walkthrough.mjs
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const candidateId = Number(process.env.NANOBIO_CANDIDATE_ID);
const viewportWidth = Number(process.env.NANOBIO_VIEWPORT_WIDTH ?? '1500');
const FRONTEND_ROOT = dirname(fileURLToPath(import.meta.url));
const PROFILE = resolve(FRONTEND_ROOT,
  '../var/playwright/candidate-version-profile');
const OUT = resolve(FRONTEND_ROOT, '../docs/screenshots');

if (!Number.isInteger(candidateId) || candidateId <= 0) {
  console.error('Set NANOBIO_CANDIDATE_ID to a candidate with at least two versions.');
  process.exit(2);
}

mkdirSync(PROFILE, { recursive: true });
mkdirSync(OUT, { recursive: true });

const { user, pass } = walkthroughCredentials();
const failures = [];
let assertionCount = 0;
const check = (label, condition, detail = '') => {
  assertionCount += 1;
  console.log(`${label.padEnd(62, '.')} ${condition ? 'ok' : 'PROBLEM'}`);
  if (!condition) failures.push(`${label}${detail ? `: ${detail}` : ''}`);
};

async function openContext() {
  return chromium.launchPersistentContext(PROFILE, {
    headless: true,
    viewport: { width: viewportWidth, height: 1050 },
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
  });
}

async function authenticate(page) {
  await page.goto(`${APP}/login`);
  if (!page.url().includes('/login')) return;
  const formAppeared = await page.locator('#username').waitFor({
    state: 'visible', timeout: 3_000,
  }).then(() => true).catch(() => false);
  // A persistent profile may already carry a valid session.  In that case
  // React redirects /login after hydration; the absent form is success only
  // when the URL has actually left the login route.
  if (!formAppeared && !page.url().includes('/login')) return;
  if (!formAppeared) throw new Error('The login route showed no login form.');
  await page.fill('#username', user);
  await page.fill('#password', pass);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.endsWith('/login'), {
    timeout: 20_000,
  });
}

async function assertVersionScreen(page, phase) {
  await page.goto(`${APP}/validation/candidates/${candidateId}/versions`);
  await page.getByRole('heading', { name: 'Version history' }).waitFor();

  const rows = page.locator('.cv__row');
  const count = await rows.count();
  check(`${phase}: history has multiple exact versions`, count >= 2,
        `found ${count}`);

  const terms = page.locator('.cv__standings dt');
  const termText = (await terms.allInnerTexts()).map((value) => value.trim().toLowerCase());
  check(`${phase}: current effective standing is named`,
        termText.includes('current effective version'));
  check(`${phase}: latest approved standing is named`,
        termText.includes('latest approved'));
  check(`${phase}: latest draft standing is named`,
        termText.includes('latest draft'));
  check(`${phase}: ambiguous latest-version label is not used`,
        !termText.includes('latest version'));
  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }));
  check(`${phase}: no page-level horizontal overflow`,
        overflow.document <= 1 && overflow.body <= 1, JSON.stringify(overflow));

  if (count >= 2) {
    const historical = rows.nth(count - 1);
    const exactLabel = (await historical.locator('strong').innerText()).trim();
    await historical.click();
    await page.reload();
    await page.getByRole('heading', { name: 'Version history' }).waitFor();
    check(`${phase}: exact historical version remains addressable after reload`,
          await page.getByRole('button', {
            name: new RegExp(`^${exactLabel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')},`),
          }).isVisible(), exactLabel);
  }

  await page.screenshot({
    path: resolve(OUT, `candidate-version-${phase}.png`), fullPage: true,
  });
}

let context = await openContext();
let page = context.pages()[0] ?? await context.newPage();
page.on('pageerror', (error) => failures.push(`page error: ${error.message}`));

try {
  await authenticate(page);
  await assertVersionScreen(page, 'before-restart');
  await context.close();

  context = await openContext();
  page = context.pages()[0] ?? await context.newPage();
  await assertVersionScreen(page, 'after-restart');
} catch (error) {
  failures.push(error instanceof Error ? error.stack ?? error.message : String(error));
} finally {
  await context.close().catch(() => undefined);
}

if (failures.length > 0) {
  console.error('\nCandidate version walkthrough failed:\n- ' + failures.join('\n- '));
  process.exit(1);
}

console.log(`\n${assertionCount} browser assertions passed at ${viewportWidth}px.`);
console.log('Candidate version history survived reload and a persistent-browser restart.');
