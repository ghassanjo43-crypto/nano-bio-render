/**
 * Live browser walkthrough of activation, reset and session management.
 *
 * What only this can prove
 * ------------------------
 * The vitest suite stubs `fetch`, so it passes against a backend that serves
 * none of these routes. The pytest suite calls the service layer and the API
 * directly, so it passes against a frontend that never calls either. Neither
 * touches a cookie jar.
 *
 * This drives a real Chromium against a running server with **three browser
 * contexts** — separate cookie jars, which is what makes a session actually
 * separate — and checks the thing that matters most and is hardest to fake:
 * **that a cookie stops working at the moment it is supposed to.** A revoked
 * session that keeps serving requests until its cache entry expires passes
 * every unit test ever written for it.
 *
 * The sequence, which is one story
 * --------------------------------
 *   an administrator creates an account and gets a link, never a password →
 *   the newcomer opens it → a bad password is refused and the link SURVIVES →
 *   a good one activates → they sign in → the link is dead on replay →
 *   they sign in twice more, see three sessions, revoke one, and that
 *   context's cookie is refused on its very next request →
 *   they change their password: this session lives, the others die →
 *   they forget it, request a reset, and the reset kills every session
 *   including the one that requested it →
 *   the administrator suspends them and the next request is refused.
 *
 * Credentials come from the environment. The newcomer's password is *chosen by
 * this script* and never leaves it, because that is exactly the property under
 * test: nobody but the account holder ever sets it.
 */

import { chromium } from 'playwright';
import { walkthroughCredentials } from './walkthrough-credentials.mjs';
import { mkdirSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { resolve } from 'node:path';

const APP = process.argv[2] ?? 'http://127.0.0.1:5173';
const OUT = resolve('../docs/screenshots');
mkdirSync(OUT, { recursive: true });

const { user: ADMIN_USER, pass: ADMIN_PASS } = walkthroughCredentials();

/**
 * The newcomer's account name, unique per run.
 *
 * Activation can only happen once per account, so a fixed name would pass on a
 * clean database and fail on the second run — which reads as a regression and
 * is not one. A per-run suffix keeps every run a genuine first activation.
 */
const STAMP = randomBytes(4).toString('hex');
const NEW_USER = `wt_activate_${STAMP}`;
const NEW_EMAIL = `wt.activate.${STAMP}@example.test`;

/**
 * Passwords this script chooses. Long, unrelated to the username, and not
 * derived from anything on a common list — they have to survive the real
 * policy, which is part of what is being checked.
 */
const FIRST_PASSWORD = `harbour-lantern-${STAMP}-quill`;
const SECOND_PASSWORD = `meridian-thicket-${STAMP}-vellum`;
const THIRD_PASSWORD = `cornice-adamant-${STAMP}-fathom`;
const TOO_SHORT = 'short1';

const problems = [];
const notes = [];
let assertions = 0;

const log = (l, v) => console.log(`${l.padEnd(68, '.')} ${v}`);
function check(label, ok, detail = '') {
  assertions += 1;
  log(label, ok ? 'ok' : 'PROBLEM');
  if (!ok) problems.push(`${label}${detail ? `: ${detail}` : ''}`);
  return ok;
}

async function shot(page, name) {
  await page.screenshot({ path: resolve(OUT, `account-${name}.png`),
                          fullPage: true });
}

/** Call the API from inside a page, so that context's cookie jar travels. */
function api(page) {
  return (path, init) => page.evaluate(
    async ([p, i]) => {
      const response = await fetch(p, i ?? undefined);
      let body = null;
      try { body = await response.json(); } catch { body = null; }
      return { status: response.status, body };
    }, [path, init ?? null]);
}

async function signIn(page, username, password) {
  await page.goto(`${APP}/login`);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/start/, { timeout: 25000 });
}

/** The session cookie for a context, or null. */
async function sessionCookie(context) {
  const cookies = await context.cookies();
  return cookies.find((c) => c.name === 'nanobio_session')?.value ?? null;
}

async function selectOrganization(page) {
  await page.waitForSelector('[data-testid="active-organization"]',
                             { timeout: 20000 }).catch(() => {});
  const trigger = page.locator('[data-testid="organization-switcher"]');
  if (await trigger.count() === 0) return null;
  await trigger.click();
  const options = page.getByRole('menuitemradio');
  await options.first().waitFor({ state: 'visible', timeout: 10000 });

  // Pick a confirmed organization. The upgrade backfill enrols everybody into
  // the legacy organization, which sorts first and is PENDING_CONFIRMATION —
  // administrative writes are refused there until it is confirmed, so taking
  // `[0]` would make every administrative check fail for a legitimate reason
  // that has nothing to do with what is being tested.
  const count = await options.count();
  for (let i = 0; i < count; i += 1) {
    const text = (await options.nth(i).textContent()) ?? '';
    if (!/awaiting confirmation/i.test(text)) {
      await options.nth(i).click();
      await page.waitForTimeout(1500);
      return text.trim();
    }
  }
  await options.first().click();
  await page.waitForTimeout(1500);
  return null;
}

async function preflight() {
  try {
    const response = await fetch(`${APP}/api/v1/account/password-policy`);
    if (response.status !== 200) {
      console.error(`The account routes are not being served at ${APP} `
                    + `(HTTP ${response.status}). Start the backend and the `
                    + `dev server first.`);
      return false;
    }
  } catch (error) {
    console.error(`Nothing is serving ${APP}: ${error.message}`);
    return false;
  }
  return true;
}

async function main() {
  if (!await preflight()) return 2;

  const browser = await chromium.launch();

  // Three separate contexts = three separate cookie jars. Two pages in one
  // context share a session, which would make every revocation check
  // meaningless.
  const adminContext = await browser.newContext();
  const deskContext = await browser.newContext();
  const laptopContext = await browser.newContext();
  const phoneContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
             + 'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
             + 'Mobile/15E148 Safari/604.1',
  });

  const admin = await adminContext.newPage();
  const desk = await deskContext.newPage();
  const laptop = await laptopContext.newPage();
  const phone = await phoneContext.newPage();

  try {
    /* ================================================================== */
    console.log('\n--- 1. An administrator creates an account -------------\n');

    await signIn(admin, ADMIN_USER, ADMIN_PASS);
    await admin.goto(`${APP}/organization`);
    const organization = await selectOrganization(admin);
    notes.push(`administering: ${organization ?? '(single organization)'}`);

    const adminApi = api(admin);
    const organizations = await adminApi('/api/v1/organizations');
    const usable = (organizations.body?.organizations ?? [])
      .find((o) => !o.awaiting_confirmation);
    if (!usable) {
      console.error('The administrator has no confirmed organization. '
                    + 'Confirm one before running this walkthrough.');
      return 2;
    }

    const created = await adminApi(
      `/api/v1/account/admin/organizations/${usable.id}/accounts`,
      { method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'X-Organization-Id': String(usable.id) },
        body: JSON.stringify({
          username: NEW_USER, email: NEW_EMAIL,
          full_name: 'Walkthrough Newcomer', role: 'researcher',
        }) });

    check('an administrator can create an account',
          created.status === 200 || created.status === 201,
          `HTTP ${created.status} ${JSON.stringify(created.body).slice(0, 200)}`);

    const serialised = JSON.stringify(created.body ?? {});
    check('the creation response carries NO password field',
          !/"password"/.test(serialised) && !/"temporary/i.test(serialised),
          serialised.slice(0, 200));
    check('it carries a one-time link instead',
          typeof created.body?.activation_link === 'string'
            && created.body.activation_link.includes('token='),
          String(created.body?.activation_link).slice(0, 60));
    check('and says the link is shown only once',
          created.body?.link_shown_once === true);

    const activationLink = created.body?.activation_link ?? '';
    const activationPath = activationLink.replace(/^https?:\/\/[^/]+/, '');

    // An administrator setting a password must be refused outright, not
    // ignored — an ignored field means the request "succeeded" and the
    // administrator believes they know the password.
    const withPassword = await adminApi(
      `/api/v1/account/admin/organizations/${usable.id}/accounts`,
      { method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'X-Organization-Id': String(usable.id) },
        body: JSON.stringify({
          username: `${NEW_USER}_x`, email: `x.${NEW_EMAIL}`,
          role: 'researcher',
          password: 'an-administrator-chosen-password',
        }) });
    check('an administrator supplying a password is REFUSED, not ignored',
          withPassword.status === 422 || withPassword.status === 400,
          `HTTP ${withPassword.status}`);

    /* ================================================================== */
    console.log('\n--- 2. The administrative screen shows no password -----\n');

    await admin.goto(`${APP}/organization`);
    await selectOrganization(admin);
    await admin.getByRole('tab', { name: /Accounts/i }).click();
    await admin.waitForSelector('[data-testid="accounts-list"]',
                                { timeout: 20000 });

    const adminText = await admin.locator('main').innerText();
    check('the accounts screen states passwords are never visible',
          /cannot see, set,\s*recover or copy/i.test(adminText));
    check('there is no "show password" control anywhere on it',
          !/show password|reveal password|view password/i.test(adminText));
    await shot(admin, 'admin-accounts');

    const row = admin.locator('[data-testid="account-row"]')
      .filter({ hasText: NEW_USER });
    check('the new account appears in the roster', await row.count() > 0);

    if (await row.count() > 0) {
      await row.locator('[data-testid="open-account"]').click();
      await admin.waitForSelector('[data-testid="account-state"]',
                                  { timeout: 15000 });
      const stateText = await row.locator('[data-testid="account-state"]')
        .innerText();
      check('it is shown as awaiting activation',
            /awaiting activation/i.test(stateText), stateText);
      const meaning = await row.locator('[data-testid="account-state-meaning"]')
        .innerText();
      check('the state explains that nobody can set the password for them',
            /nobody, including an administrator/i.test(meaning), meaning);
      check('membership state is shown separately from account state',
            await row.locator('[data-testid="membership-status"]').count() > 0);
    }

    /* ================================================================== */
    console.log('\n--- 3. Activation: a bad password must not spend it ----\n');

    await desk.goto(`${APP}${activationPath}`);
    await desk.waitForSelector('#new-password', { timeout: 20000 });
    check('the activation link opens the set-password screen',
          await desk.locator('#new-password').count() > 0);
    await shot(desk, 'activate-form');

    await desk.fill('#new-password', TOO_SHORT);
    await desk.fill('#confirm-password', TOO_SHORT);
    await desk.click('[data-testid="submit-password"]');
    await desk.waitForSelector('[data-testid="password-rejected"]',
                               { timeout: 15000 });

    check('a password that fails policy is refused',
          await desk.locator('[data-testid="password-rejected"]').count() > 0);
    check('and the form is still usable — the link was NOT consumed',
          await desk.locator('[data-testid="submit-password"]').count() > 0);
    check('the screen says the link is still valid',
          /link is still valid/i.test(
            await desk.locator('[data-testid="password-rejected"]').innerText()));
    await shot(desk, 'activate-rejected');

    // The real proof: use the same link again with a good password.
    await desk.fill('#new-password', FIRST_PASSWORD);
    await desk.fill('#confirm-password', FIRST_PASSWORD);
    await desk.click('[data-testid="submit-password"]');
    await desk.waitForSelector('[data-testid="go-to-sign-in"]',
                               { timeout: 20000 });
    check('the SAME link then activates the account with a good password',
          await desk.locator('[data-testid="go-to-sign-in"]').count() > 0);
    await shot(desk, 'activate-done');

    /* ================================================================== */
    console.log('\n--- 4. Replay of a used link is refused ----------------\n');

    await laptop.goto(`${APP}${activationPath}`);
    await laptop.waitForSelector('#new-password', { timeout: 20000 });
    await laptop.fill('#new-password', SECOND_PASSWORD);
    await laptop.fill('#confirm-password', SECOND_PASSWORD);
    await laptop.click('[data-testid="submit-password"]');
    await laptop.waitForSelector('[data-testid="link-unusable"]',
                                 { timeout: 20000 });

    const replayText = await laptop.locator('[data-testid="link-unusable"]')
      .innerText();
    check('replaying a used activation link is refused', true);
    check('the refusal does not say the account exists',
          !/no such account|does not exist|already active|unknown user/i
            .test(replayText), replayText.slice(0, 120));
    await shot(laptop, 'activate-replay');

    /* ================================================================== */
    console.log('\n--- 5. Sign in, on three devices -----------------------\n');

    await signIn(desk, NEW_USER, FIRST_PASSWORD);
    check('the newcomer can sign in with the password THEY chose', true);
    const deskCookie = await sessionCookie(deskContext);
    check('a session cookie was issued', Boolean(deskCookie));

    await signIn(laptop, NEW_USER, FIRST_PASSWORD);
    await signIn(phone, NEW_USER, FIRST_PASSWORD);
    const laptopCookie = await sessionCookie(laptopContext);
    const phoneCookie = await sessionCookie(phoneContext);
    check('three separate contexts hold three different session cookies',
          new Set([deskCookie, laptopCookie, phoneCookie]).size === 3);

    await desk.goto(`${APP}/account/security`);
    await desk.waitForSelector('[data-testid="session-list"]', { timeout: 20000 });
    const rows = await desk.locator('[data-testid="session-list"] li').count();
    check('all three sessions are listed', rows === 3, `saw ${rows}`);
    check('exactly one is marked as the current device',
          await desk.locator('[data-testid="session-current"]').count() === 1);
    check('the current session offers sign-out, not revoke',
          await desk.locator('[data-testid="session-current"] '
                             + '[data-testid="sign-out-this-session"]').count() === 1);
    await shot(desk, 'sessions');

    /* ================================================================== */
    console.log('\n--- 6. Revoking another session takes effect at once ---\n');

    // Find the row that is NOT this device, and end it.
    const other = desk.locator('[data-testid="session-other"]').first();
    await other.locator('[data-testid="revoke-session"]').click();
    const dialog = desk.getByRole('dialog');
    await dialog.waitFor({ state: 'visible', timeout: 10000 });
    await dialog.getByRole('textbox').first().fill(NEW_USER);
    await dialog.getByRole('button', { name: /^sign out$/i }).click();
    await desk.waitForSelector('[data-testid="session-action-notice"]',
                               { timeout: 20000 });
    check('revoking another session reports success', true);

    // Which context lost its session? Ask both, using their own cookies.
    const laptopAfter = await api(laptop)('/api/v1/auth/me');
    const phoneAfter = await api(phone)('/api/v1/auth/me');
    const revokedCount = [laptopAfter, phoneAfter]
      .filter((r) => r.status === 401).length;
    check('exactly one of the other two sessions is now refused 401',
          revokedCount === 1,
          `laptop ${laptopAfter.status}, phone ${phoneAfter.status}`);

    const deskStillOk = await api(desk)('/api/v1/auth/me');
    check('the revoking session is unaffected', deskStillOk.status === 200,
          `HTTP ${deskStillOk.status}`);

    const survivor = laptopAfter.status === 401 ? phone : laptop;
    const survivorContext = laptopAfter.status === 401
      ? phoneContext : laptopContext;

    /* ================================================================== */
    console.log('\n--- 7. Sign out everywhere else ------------------------\n');

    await desk.reload();
    await desk.waitForSelector('[data-testid="session-list"]', { timeout: 20000 });
    await desk.locator('[data-testid="sign-out-everywhere"]').click();
    const allDialog = desk.getByRole('dialog');
    await allDialog.waitFor({ state: 'visible', timeout: 10000 });
    await allDialog.getByRole('textbox').first().fill(NEW_USER);
    await allDialog.getByRole('button', { name: /sign out everywhere else/i })
      .click();
    await desk.waitForSelector('[data-testid="session-action-notice"]',
                               { timeout: 20000 });

    const survivorAfterAll = await api(survivor)('/api/v1/auth/me');
    check('sign-out-everywhere refuses the remaining other session',
          survivorAfterAll.status === 401, `HTTP ${survivorAfterAll.status}`);
    check('and keeps the session that asked for it',
          (await api(desk)('/api/v1/auth/me')).status === 200);
    check('the notice says this device is still signed in',
          /still signed in here/i.test(
            await desk.locator('[data-testid="session-action-notice"]').innerText()));

    /* ================================================================== */
    console.log('\n--- 8. Password change keeps this session --------------\n');

    // Sign the survivor back in, so there is something for the change to end.
    await signIn(survivor, NEW_USER, FIRST_PASSWORD);
    const survivorCookieBefore = await sessionCookie(survivorContext);
    const deskCookieBefore = await sessionCookie(deskContext);

    await desk.goto(`${APP}/account/security`);
    await desk.waitForSelector('#current-password', { timeout: 20000 });
    await desk.fill('#current-password', FIRST_PASSWORD);
    await desk.fill('#change-new-password', SECOND_PASSWORD);
    await desk.fill('#change-confirm-password', SECOND_PASSWORD);
    await desk.click('[data-testid="submit-password-change"]');
    await desk.waitForSelector('[data-testid="password-change-notice"]',
                               { timeout: 25000 });

    check('the password change reports success', true);
    check('this session survives the change',
          (await api(desk)('/api/v1/auth/me')).status === 200);
    check('every OTHER session is ended by it',
          (await api(survivor)('/api/v1/auth/me')).status === 401);
    check('the notice explains both halves',
          /still signed in here/i.test(
            await desk.locator('[data-testid="password-change-notice"]').innerText()));
    await shot(desk, 'password-changed');

    // The old cookie value must not work even if replayed by hand.
    const replayContext = await browser.newContext();
    await replayContext.addCookies([{
      name: 'nanobio_session', value: survivorCookieBefore ?? 'none',
      domain: '127.0.0.1', path: '/',
    }]);
    const replayPage = await replayContext.newPage();
    await replayPage.goto(`${APP}/login`);
    const replayed = await api(replayPage)('/api/v1/auth/me');
    check('an ended session cookie is refused when replayed verbatim',
          replayed.status === 401, `HTTP ${replayed.status}`);
    await replayContext.close();

    check('the old password no longer signs in', await (async () => {
      const probe = await browser.newContext();
      const probePage = await probe.newPage();
      await probePage.goto(`${APP}/login`);
      const result = await api(probePage)('/api/v1/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: NEW_USER, password: FIRST_PASSWORD }),
      });
      await probe.close();
      return result.status === 401;
    })());

    /* --- session fixation ------------------------------------------- */
    // Signing in again in a context that ALREADY holds a session must issue a
    // new cookie and kill the old one. This was a note comparing two values
    // captured many operations apart, which proved nothing: they differed for
    // any of a dozen reasons. Done properly it is the session-fixation check —
    // an attacker who can plant a cookie value in somebody's browser before
    // they sign in must not find that value authenticated afterwards.
    const fixation = await browser.newContext();
    const fixationPage = await fixation.newPage();

    await signIn(fixationPage, NEW_USER, SECOND_PASSWORD);
    const beforeSecondSignIn = await sessionCookie(fixation);

    // The second sign-in goes through the API rather than the login form,
    // because the form is unreachable once a session exists — the app
    // redirects an authenticated visitor away from /login, which is correct
    // behaviour and not what is being tested. What is being tested is the
    // protocol-level question: when a sign-in arrives carrying an existing
    // session cookie, is a new one issued and the old one killed?
    //
    // `context.request` shares this context's cookie jar, so the request
    // genuinely carries the old cookie and the new Set-Cookie lands back in
    // the same jar.
    const secondSignIn = await fixation.request.post(
      `${APP}/api/v1/auth/login`,
      { headers: { 'Content-Type': 'application/json', 'Origin': APP },
        data: { username: NEW_USER, password: SECOND_PASSWORD },
        failOnStatusCode: false });
    check('a second sign-in carrying an existing session succeeds',
          secondSignIn.status() === 200, `HTTP ${secondSignIn.status()}`);
    const afterSecondSignIn = await sessionCookie(fixation);

    check('signing in again issues a DIFFERENT session cookie',
          Boolean(beforeSecondSignIn) && Boolean(afterSecondSignIn)
            && beforeSecondSignIn !== afterSecondSignIn);

    // And the previous value is dead, not merely replaced in the jar.
    const staleContext = await browser.newContext();
    await staleContext.addCookies([{
      name: 'nanobio_session', value: beforeSecondSignIn ?? 'none',
      domain: '127.0.0.1', path: '/',
    }]);
    const stalePage = await staleContext.newPage();
    await stalePage.goto(`${APP}/login`);
    const staleResult = await api(stalePage)('/api/v1/auth/me');
    check('the cookie replaced at sign-in is REFUSED, not merely replaced',
          staleResult.status === 401, `HTTP ${staleResult.status}`);

    // Positive control: the new one works.
    const newCookieWorks = await fixation.request.get(
      `${APP}/api/v1/auth/me`, { failOnStatusCode: false });
    check('and the new session cookie authenticates normally',
          newCookieWorks.status() === 200, `HTTP ${newCookieWorks.status()}`);

    await staleContext.close();
    await fixation.close();

    notes.push(`first-sign-in cookie differed from later cookie: `
               + `${deskCookieBefore !== deskCookie ? 'yes' : 'no'}`);

    /* ================================================================== */
    console.log('\n--- 9. Forgotten password, and a reset -----------------\n');

    const anon = await browser.newContext();
    const anonPage = await anon.newPage();

    // The generic response, for a real account and a fictional one.
    await anonPage.goto(`${APP}/account/forgot`);
    await anonPage.fill('#forgot-username', NEW_USER);
    await anonPage.click('[data-testid="request-reset"]');
    await anonPage.waitForSelector('[data-testid="forgot-confirmation"]',
                                   { timeout: 20000 });
    const realAnswer = await anonPage
      .locator('[data-testid="forgot-confirmation"]').innerText();

    await anonPage.goto(`${APP}/account/forgot`);
    await anonPage.fill('#forgot-username', `definitely_not_a_user_${STAMP}`);
    await anonPage.click('[data-testid="request-reset"]');
    await anonPage.waitForSelector('[data-testid="forgot-confirmation"]',
                                   { timeout: 20000 });
    const fakeAnswer = await anonPage
      .locator('[data-testid="forgot-confirmation"]').innerText();

    check('the forgotten-password answer is identical for a real and a '
          + 'non-existent account',
          realAnswer.trim() === fakeAnswer.trim(),
          `real=${realAnswer.slice(0, 60)} fake=${fakeAnswer.slice(0, 60)}`);
    check('and it discloses nothing about whether the account exists',
          !/no such|not found|unknown user|does not exist/i.test(realAnswer));
    await shot(anonPage, 'forgot-confirmation');
    await anon.close();

    // Now an administrator-initiated reset, so the link is obtainable.
    const firstReset = await adminApi(
      `/api/v1/account/admin/organizations/${usable.id}/accounts/`
      + `${created.body.user_id}/reset`,
      { method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'X-Organization-Id': String(usable.id) },
        body: '{}' });
    check('an administrator can initiate a password reset',
          firstReset.status === 200, `HTTP ${firstReset.status}`);
    check('the reset response carries a link and no password',
          typeof firstReset.body?.reset_link === 'string'
            && !/"password"/.test(JSON.stringify(firstReset.body)));

    // Issue a SECOND one. The first must die.
    const secondReset = await adminApi(
      `/api/v1/account/admin/organizations/${usable.id}/accounts/`
      + `${created.body.user_id}/reset`,
      { method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'X-Organization-Id': String(usable.id) },
        body: '{}' });

    const supersededPath = firstReset.body.reset_link.replace(/^https?:\/\/[^/]+/, '');
    const livePath = secondReset.body.reset_link.replace(/^https?:\/\/[^/]+/, '');

    const superseded = await browser.newContext();
    const supersededPage = await superseded.newPage();
    await supersededPage.goto(`${APP}${supersededPath}`);
    await supersededPage.waitForSelector('#new-password', { timeout: 20000 });
    await supersededPage.fill('#new-password', THIRD_PASSWORD);
    await supersededPage.fill('#confirm-password', THIRD_PASSWORD);
    await supersededPage.click('[data-testid="submit-password"]');
    await supersededPage.waitForSelector('[data-testid="link-unusable"]',
                                         { timeout: 20000 });
    check('a superseded reset link is refused once a newer one exists', true);
    check('the superseded refusal is worded identically to a replay',
          (await supersededPage.locator('[data-testid="link-unusable"]')
            .innerText()).includes('cannot be used'));
    await shot(supersededPage, 'reset-superseded');
    await superseded.close();

    /* ================================================================== */
    console.log('\n--- 10. A reset ends EVERY session ---------------------\n');

    // Sign in twice more so there is something to end.
    await signIn(survivor, NEW_USER, SECOND_PASSWORD);
    check('the desk session is still live before the reset',
          (await api(desk)('/api/v1/auth/me')).status === 200);

    const resetContext = await browser.newContext();
    const resetPage = await resetContext.newPage();
    await resetPage.goto(`${APP}${livePath}`);
    await resetPage.waitForSelector('#new-password', { timeout: 20000 });
    await resetPage.fill('#new-password', THIRD_PASSWORD);
    await resetPage.fill('#confirm-password', THIRD_PASSWORD);
    await resetPage.click('[data-testid="submit-password"]');
    await resetPage.waitForSelector('[data-testid="go-to-sign-in"]',
                                    { timeout: 25000 });
    check('the live reset link sets a new password', true);

    check('a reset ends the session that was signed in elsewhere',
          (await api(desk)('/api/v1/auth/me')).status === 401,
          'a reset must end EVERY session — none can be shown to belong to '
          + 'the person who held the link');
    check('and every other one too',
          (await api(survivor)('/api/v1/auth/me')).status === 401);
    await resetContext.close();

    /* ================================================================== */
    console.log('\n--- 11. Suspension takes effect immediately ------------\n');

    await signIn(desk, NEW_USER, THIRD_PASSWORD);
    check('the newcomer signs in with the reset password',
          (await api(desk)('/api/v1/auth/me')).status === 200);

    const suspended = await adminApi(
      `/api/v1/account/admin/organizations/${usable.id}/accounts/`
      + `${created.body.user_id}/state`,
      { method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'X-Organization-Id': String(usable.id) },
        body: JSON.stringify({ state: 'suspended',
                               reason: 'walkthrough verification' }) });
    check('an administrator can suspend the account',
          suspended.status === 200, `HTTP ${suspended.status}`);
    check('suspension states that attribution is preserved',
          /attribution and audit history are unchanged/i
            .test(String(suspended.body?.notice)),
          String(suspended.body?.notice).slice(0, 120));

    check('the suspended account\'s NEXT request is refused',
          (await api(desk)('/api/v1/auth/me')).status === 401);

    const suspendedLogin = await (async () => {
      const probe = await browser.newContext();
      const probePage = await probe.newPage();
      await probePage.goto(`${APP}/login`);
      const result = await api(probePage)('/api/v1/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: NEW_USER, password: THIRD_PASSWORD }),
      });
      await probe.close();
      return result;
    })();
    check('a suspended account cannot sign in again',
          suspendedLogin.status === 401 || suspendedLogin.status === 403,
          `HTTP ${suspendedLogin.status}`);

    // Restore, and confirm it is reversible without a new password.
    const restored = await adminApi(
      `/api/v1/account/admin/organizations/${usable.id}/accounts/`
      + `${created.body.user_id}/state`,
      { method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'X-Organization-Id': String(usable.id) },
        body: JSON.stringify({ state: 'active', reason: 'walkthrough restore' }) });
    check('an administrator can restore access', restored.status === 200);

    await signIn(desk, NEW_USER, THIRD_PASSWORD);
    check('a restored account signs in with its EXISTING password '
          + '(no reset was needed)',
          (await api(desk)('/api/v1/auth/me')).status === 200);

    /* ================================================================== */
    console.log('\n--- 12. Mobile layout at 390px -------------------------\n');

    await signIn(phone, NEW_USER, THIRD_PASSWORD);
    await phone.goto(`${APP}/account/security`);
    await phone.waitForSelector('[data-testid="session-list"]', { timeout: 20000 });

    const overflow = await phone.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    check('the security screen does not overflow horizontally at 390px',
          overflow.scrollWidth <= overflow.clientWidth + 1,
          `${overflow.scrollWidth} > ${overflow.clientWidth}`);

    const touchTargets = await phone.evaluate(() => {
      const buttons = [...document.querySelectorAll(
        '[data-testid="session-list"] button')];
      return buttons.map((b) => b.getBoundingClientRect().height);
    });
    check('session controls meet the 44px touch target on mobile',
          touchTargets.length > 0 && touchTargets.every((h) => h >= 40),
          JSON.stringify(touchTargets));
    await shot(phone, 'mobile-sessions');

    await phone.goto(`${APP}/account/forgot`);
    await phone.waitForSelector('#forgot-username', { timeout: 20000 });
    const forgotOverflow = await phone.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    check('the forgotten-password screen fits at 390px',
          forgotOverflow.scrollWidth <= forgotOverflow.clientWidth + 1,
          `${forgotOverflow.scrollWidth} > ${forgotOverflow.clientWidth}`);
    await shot(phone, 'mobile-forgot');

    /* ================================================================== */
    console.log('\n--- 13. Cookies, CSRF and navigation -------------------\n');

    const jar = await deskContext.cookies();
    const session = jar.find((c) => c.name === 'nanobio_session');
    check('the session cookie is HttpOnly', session?.httpOnly === true);
    check('the session cookie declares SameSite',
          ['Lax', 'Strict'].includes(session?.sameSite ?? ''),
          String(session?.sameSite));
    check('the session cookie is host-only',
          !session?.domain?.startsWith('.'), String(session?.domain));

    // A cross-origin credentialed write must be refused by the origin check.
    //
    // Driven through Playwright's request context, NOT through `page.evaluate`
    // and `fetch`. `Origin` is a forbidden header name: a browser silently
    // drops any attempt to set it from script and sends the page's real
    // origin instead. The first version of this check did exactly that, so it
    // sent a same-origin request, got a legitimate 200, and reported the CSRF
    // protection as broken when it was working — a false alarm that would have
    // cost somebody an afternoon.
    //
    // The request context shares this browser context's cookie jar, so the
    // request is genuinely credentialed, and it is not a browser, so it can
    // set the header the check is about.
    const csrfResponse = await deskContext.request.post(
      `${APP}/api/v1/account/sessions/revoke-all`,
      { headers: { 'Content-Type': 'application/json',
                   'Origin': 'https://attacker.example.test' },
        data: {}, failOnStatusCode: false });
    check('a credentialed write claiming a foreign Origin is refused',
          csrfResponse.status() === 403, `HTTP ${csrfResponse.status()}`);

    // Positive control: the same request from the real origin is not refused
    // by the origin check. Without this, a middleware that refused everything
    // would pass the assertion above.
    const sameOrigin = await deskContext.request.post(
      `${APP}/api/v1/account/sessions/revoke-all`,
      { headers: { 'Content-Type': 'application/json', 'Origin': APP },
        data: {}, failOnStatusCode: false });
    check('and the same write from the real origin is allowed through',
          sameOrigin.status() === 200, `HTTP ${sameOrigin.status()}`);

    // Browser navigation must not resurrect a signed-out screen.
    await desk.goto(`${APP}/account/security`);
    await desk.waitForSelector('[data-testid="session-list"]', { timeout: 20000 });
    await desk.goto(`${APP}/start`);
    await desk.goBack();
    await desk.waitForTimeout(1500);
    check('navigating back to the security screen still requires a session',
          (await api(desk)('/api/v1/auth/me')).status === 200);

    /* ================================================================== */
    console.log('\n--- 14. Security activity ------------------------------\n');

    await desk.goto(`${APP}/account/security`);
    await desk.waitForSelector('[data-testid="security-activity"]',
                               { timeout: 20000 });
    const activity = await desk.locator('[data-testid="security-activity"]')
      .innerText();
    check('recent security activity is shown', activity.length > 0);
    check('it is rendered in words, not raw event codes',
          !/LOGIN_SUCCEEDED|PASSWORD_CHANGED/.test(activity));
    check('it records the password change', /Password changed/i.test(activity));
    check('no password or token appears in it',
          !activity.includes(FIRST_PASSWORD)
            && !activity.includes(SECOND_PASSWORD)
            && !activity.includes(THIRD_PASSWORD)
            && !activity.includes(activationLink));
    await shot(desk, 'security-activity');

    /* ================================================================== */
    console.log('\n--- 15. Nothing leaked into client storage -------------\n');

    const storage = await desk.evaluate(() => JSON.stringify({
      local: { ...localStorage }, session: { ...sessionStorage },
    }));
    check('no password is in localStorage or sessionStorage',
          !storage.includes(FIRST_PASSWORD) && !storage.includes(SECOND_PASSWORD)
            && !storage.includes(THIRD_PASSWORD));
    check('no activation or reset token is in client storage',
          !storage.includes('token=') || !storage.includes(activationLink));

  } catch (error) {
    problems.push(`the walkthrough threw: ${error.message}`);
    console.error(error);
  } finally {
    await browser.close();
  }

  console.log(`\n${assertions} assertions run.`);
  for (const note of notes) console.log(`note: ${note}`);
  console.log(`note: the newcomer account ${NEW_USER} was created by this run `
              + `and is left suspended-then-restored; remove it with `
              + `scripts/walkthrough_cleanup.py.`);

  if (problems.length) {
    console.log(`\n${problems.length} problem(s):`);
    for (const problem of problems) console.log(`  - ${problem}`);
    return 1;
  }
  console.log('\nAccount and session workflows verified in a real browser.');
  return 0;
}

main().then((code) => process.exit(code));
