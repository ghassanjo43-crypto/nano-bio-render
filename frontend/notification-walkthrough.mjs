/** Real-browser verification for persistent, authorized in-app notifications. */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const width = Number(process.env.NANOBIO_VIEWPORT_WIDTH ?? '1500');
const restarted = process.env.NANOBIO_EXPECT_RESTART_STATE === '1';
const root = dirname(fileURLToPath(import.meta.url));
const profile = resolve(root, '../var/playwright/notification-profile');
mkdirSync(profile, { recursive: true });
const failures = [];
let assertions = 0;
const check = (name, value, detail = '') => {
  assertions += 1;
  console.log(`${name.padEnd(60, '.')} ${value ? 'ok' : 'PROBLEM'}`);
  if (!value) failures.push(`${name}${detail ? `: ${detail}` : ''}`);
};

const context = await chromium.launchPersistentContext(profile, {
  headless: true, viewport: { width, height: 950 },
  args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = context.pages()[0] ?? await context.newPage();
page.on('pageerror', (error) => failures.push(`page error: ${error.message}`));

try {
  await page.goto(`${APP}/notifications`);
  const landing = await Promise.race([
    page.locator('#username').waitFor().then(() => 'login'),
    page.getByRole('heading', { name: 'Notifications' }).waitFor().then(() => 'notifications'),
  ]);
  if (landing === 'login') {
    const { user, pass } = walkthroughCredentials();
    await page.fill('#username', user);
    await page.fill('#password', pass);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.endsWith('/login'));
  }
  await page.goto(`${APP}/notifications`);
  await page.getByRole('heading', { name: 'Notifications' }).waitFor();
  check('notification center is reachable', page.url().endsWith('/notifications'));
  const apiList = await page.request.get(`${APP}/api/v1/organizations/notifications/mine`);
  const apiBody = await apiList.json();
  const countResponse = await page.request.get(`${APP}/api/v1/organizations/notifications/unread-count`);
  const countBody = await countResponse.json();
  check('notification list HTTP contract succeeds', apiList.ok());
  check('HTTP contract returns notification rows', Array.isArray(apiBody.notifications));
  check('authorized recipient has exactly three records', apiBody.notifications.length === 3, JSON.stringify(apiBody));
  check('retried revision event created exactly one notification', apiBody.notifications.filter((row) => row.event === 'candidate_revision_created').length === 1);
  check('safe revision event is visible', await page.getByText('A candidate revision was created.').isVisible());
  check('safe recalculation event is visible', await page.getByText('A candidate version requires recalculation.').isVisible());
  check('safe inaccessible target state is visible', await page.getByText('The referenced record is no longer accessible.').isVisible());
  check('inaccessible target has no link', await page.getByText('Stored results require attention.').locator('..').getByRole('link').count() === 0);
  check('authorized record link is present', await page.getByRole('link', { name: 'Open record' }).first().isVisible());
  if (countBody.unread_count > 0) await page.locator('.shell__notification-count').waitFor();
  const badges = await page.locator('.shell__notification-count').allInnerTexts();
  check('header unread badge matches API count', countBody.unread_count === (badges[0] ? Number(badges[0]) : 0), JSON.stringify({badges, countBody}));
  if (!restarted) {
    check('three unread notifications are visible', await page.getByText('Unread').count() === 3);
    await page.getByRole('button', { name: 'Mark as read' }).first().click();
    await page.waitForFunction(() => document.querySelectorAll('.notification--unread').length === 2);
    check('marking one notification updates the row', await page.getByText('Unread').count() === 2);
    await page.reload();
    await page.getByRole('heading', { name: 'Notifications' }).waitFor();
    check('single-notification read state persists', await page.getByText('Unread').count() === 2);
    await page.getByRole('button', { name: 'Mark all as read' }).click();
    await page.waitForFunction(() => document.querySelectorAll('.notification--unread').length === 0);
    check('bulk read updates every row', await page.getByText('Unread').count() === 0);
  }
  await page.reload();
  await page.getByRole('heading', { name: 'Notifications' }).waitFor();
  check('read state survives reload', await page.getByText('Unread').count() === 0);
  const afterCount = await (await page.request.get(`${APP}/api/v1/organizations/notifications/unread-count`)).json();
  check('bulk read updates API unread count and badge', afterCount.unread_count === 0 && await page.locator('.shell__notification-count').count() === 0);
  if (restarted) check('records survive backend restart', apiBody.notifications.length === 3);
  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }));
  check('no page-level horizontal overflow', overflow.document <= 1 && overflow.body <= 1, JSON.stringify(overflow));
  const credentialVisible = await page.evaluate(
    (secret) => Boolean(secret) && (document.body.textContent ?? '').includes(secret),
    process.env.NANOBIO_WALKTHROUGH_PASSWORD ?? '');
  check('generic text contains no fixture credentials', !credentialVisible);

  for (const username of ['notification_foreign', 'notification_unassigned', 'notification_revoked']) {
    const isolated = await context.browser().newContext({ viewport: { width, height: 950 } });
    const other = await isolated.newPage();
    await other.goto(`${APP}/login`);
    await other.fill('#username', username);
    await other.fill('#password', process.env.NANOBIO_WALKTHROUGH_PASSWORD);
    await other.click('button[type="submit"]');
    await other.waitForURL((url) => !url.pathname.endsWith('/login'));
    const response = await other.request.get(`${APP}/api/v1/organizations/notifications/mine`);
    const body = await response.json();
    check(`${username} cannot see recipient notifications`, response.ok() && body.notifications.length === 0, JSON.stringify(body));
    await isolated.close();
  }
} catch (error) {
  failures.push(error instanceof Error ? error.stack ?? error.message : String(error));
} finally {
  await context.close();
}

if (failures.length) {
  console.error('\nNotification walkthrough failed:\n- ' + failures.join('\n- '));
  process.exit(1);
}
console.log(`\n${assertions} browser assertions passed at ${width}px.`);
