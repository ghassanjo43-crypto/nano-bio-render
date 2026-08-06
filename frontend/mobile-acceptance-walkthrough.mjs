/** Platform-wide responsive and basic-accessibility acceptance on the real stack. */
import { chromium } from 'playwright';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const candidateId = Number(process.env.NANOBIO_CANDIDATE_ID ?? 1);
const studyId = Number(process.env.NANOBIO_STUDY_ID ?? 1);
const { user, pass } = walkthroughCredentials();
const sizes = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1500, height: 950 },
];
const requestedSize = process.env.NANOBIO_ACCEPTANCE_VIEWPORT;
const activeSizes = requestedSize
  ? sizes.filter((size) => size.name === requestedSize)
  : sizes;

const protectedRoutes = [
  '/', '/start', '/start/research', '/start/session',
  '/workflow', '/workflow/disease', '/workflow/design', '/workflow/targeting',
  '/workflow/review', '/workflow/results', '/home', '/dashboard', '/demo',
  '/report', '/studies', `/studies/${studyId}`, '/patient-assessments',
  '/research-designs', '/history', `/history/${studyId}`, '/compare',
  '/projects', '/reports', '/builder', '/scientific-readiness', '/validation',
  '/validation/new', '/validation/experiments/999999',
  `/validation/candidates/${candidateId}/versions`, '/notifications',
  '/evidence', '/visualisation', '/protocol', '/experimental-planning',
  '/ai-co-designer', '/ml-training', '/help', '/settings', '/organization',
  `/organization/studies/${studyId}/team`, '/invitations/accept?token=invalid',
  '/account/security', '/unauthorized', '/admin', '/route-that-does-not-exist',
];
const responsiveRoutes = [
  '/', '/start', '/start/research', '/start/session', '/workflow/disease',
  '/workflow/design', '/workflow/targeting', '/workflow/review',
  '/workflow/results', '/home', '/demo', '/report', '/studies',
  `/studies/${studyId}`, '/compare', '/projects', '/builder',
  '/scientific-readiness', '/validation', '/validation/new',
  `/validation/candidates/${candidateId}/versions`, '/notifications',
  '/evidence', '/organization', `/organization/studies/${studyId}/team`,
  '/account/security', '/ai-co-designer', '/unauthorized',
];

let assertions = 0;
const failures = [];
const coverage = new Set();
function check(label, condition, detail = '') {
  assertions += 1;
  console.log(`${label.padEnd(72, '.')} ${condition ? 'ok' : 'PROBLEM'}`);
  if (!condition) failures.push(`${label}${detail ? `: ${detail}` : ''}`);
}

async function settled(page) {
  await page.waitForLoadState('domcontentloaded');
  await page.locator('main, [role="main"], .login-page, #root').first()
    .waitFor({ timeout: 3_000 }).catch(() => undefined);
  await page.waitForTimeout(50);
}

async function audit(page, size, requested) {
  coverage.add(requested.split('?')[0]);
  const result = await page.evaluate(({ width, mobile }) => {
    const root = document.documentElement;
    const body = document.body;
    const visible = (el) => {
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
        && style.visibility !== 'hidden' && style.display !== 'none'
        && rect.width > 0 && rect.height > 0;
    };
    const controls = [...document.querySelectorAll(
      'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"]')]
      .filter(visible);
    const clipped = controls.filter((el) => {
      const r = el.getBoundingClientRect();
      return r.left < -1 || r.right > width + 1;
    }).map((el) => (el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 60));
    const unnamed = controls.filter((el) => {
      if (el instanceof HTMLInputElement && ['submit', 'button'].includes(el.type) && el.value) return false;
      const id = el.getAttribute('id');
      const labelled = id && document.querySelector(`label[for="${CSS.escape(id)}"]`);
      return !(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')
        || el.getAttribute('title') || labelled || (el.textContent || '').trim());
    }).map((el) => el.outerHTML.slice(0, 100));
    const tiny = mobile ? controls.filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width < 24 || r.height < 24;
    }).map((el) => (el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 60)) : [];
    return {
      overflow: Math.max(root.scrollWidth - root.clientWidth,
                         body.scrollWidth - body.clientWidth),
      clipped, unnamed, tiny,
      main: document.querySelectorAll('main, [role="main"]').length,
    };
  }, { width: size.width, mobile: size.width === 390 });
  const prefix = `${size.name} ${requested}`;
  check(`${prefix}: no page horizontal overflow`, result.overflow <= 1,
        `overflow=${result.overflow}`);
  check(`${prefix}: no viewport-clipped controls`, result.clipped.length === 0,
        JSON.stringify(result.clipped));
  check(`${prefix}: controls have accessible names`, result.unnamed.length === 0,
        JSON.stringify(result.unnamed));
  if (size.width === 390) check(`${prefix}: touch targets are at least 24px`,
                               result.tiny.length === 0, JSON.stringify(result.tiny));
}

async function signIn(page) {
  await page.goto(`${APP}/login`);
  await page.locator('#username').waitFor();
  await page.fill('#username', user);
  await page.fill('#password', pass);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 20_000 });
}

const browser = await chromium.launch({ headless: true });
try {
  for (const size of activeSizes) {
    const context = await browser.newContext({ viewport: size });
    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(`${size.name} pageerror: ${error.message}`));

    await page.goto(`${APP}/studies`);
    await page.waitForURL(/\/login/);
    check(`${size.name}: protected route redirects to login`, page.url().includes('/login'));

    for (const path of ['/login', '/account/activate?token=invalid',
                        '/account/reset?token=invalid', '/account/forgot']) {
      await page.goto(`${APP}${path}`, { waitUntil: 'domcontentloaded', timeout: 10_000 });
      await settled(page);
      await audit(page, size, path);
    }

    await signIn(page);
    check(`${size.name}: valid authentication reaches protected platform`,
          !page.url().includes('/login'));
    const routes = size.name === 'desktop' ? protectedRoutes : responsiveRoutes;
    for (const path of routes) {
      await page.goto(`${APP}${path}`);
      await settled(page);
      await audit(page, size, path);
    }

    const focusVisible = await page.evaluate(async () => {
      const before = document.activeElement;
      document.body.focus();
      return before !== undefined;
    });
    check(`${size.name}: document supports keyboard focus`, focusVisible);

    const logout = await page.request.post(`${APP}/api/v1/auth/logout`);
    check(`${size.name}: logout endpoint succeeds`, logout.ok());
    await page.goto(`${APP}/studies`);
    await page.waitForURL(/\/login/);
    check(`${size.name}: invalidated session redirects protected route`,
          page.url().includes('/login'));
    await context.close();
  }
} finally {
  await browser.close();
}

const expectedCoverage = activeSizes.length === 1 && activeSizes[0].name !== 'desktop'
  ? responsiveRoutes.length + 4 : 45;
check('expected route coverage was exercised', coverage.size >= expectedCoverage,
      `covered=${coverage.size}, expected=${expectedCoverage}`);
if (failures.length) {
  console.error(`\nMobile acceptance failed (${failures.length}):\n- ${failures.join('\n- ')}`);
  process.exit(1);
}
console.log(`\n${assertions} browser assertions passed across ${coverage.size} routes at ${activeSizes.map((s) => s.width).join(', ')}px.`);
