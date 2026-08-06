/**
 * Credentials for the Playwright walkthroughs, from the environment.
 *
 * These scripts previously carried `const USER` and `const PASS` as literals,
 * repeated across all seven of them. Three problems with that, in increasing
 * order of seriousness:
 *
 * 1. A working password sat in plaintext in seven committed files, and shipped
 *    in every source archive built from them.
 * 2. Changing the account meant editing seven files, so in practice it never
 *    changed.
 * 3. The moment one of these scripts is pointed at anything shared, the
 *    committed literal is a real credential for a real system.
 *
 * Reading them from the environment fixes all three, but only if a missing
 * variable *stops* the run. A walkthrough that silently fell back to a default
 * would reintroduce the literal with extra steps, and one that failed with
 * `TypeError: cannot read property 'fill' of null` twelve seconds into a
 * browser session would tell the operator nothing about what to fix.
 *
 * Usage:
 *
 *     import { walkthroughCredentials } from './walkthrough-credentials.mjs';
 *     const { user, pass } = walkthroughCredentials();
 */

export const USER_VAR = 'NANOBIO_WALKTHROUGH_USER';
export const PASS_VAR = 'NANOBIO_WALKTHROUGH_PASSWORD';

/**
 * Build the guidance shown when a variable is missing.
 *
 * Deliberately concrete: the operator gets the variable names, both shell
 * forms, and a pointer to the account-creation script. An error that says only
 * "credentials not configured" costs a search.
 */
function guidance(missing) {
  return [
    '',
    `Walkthrough credentials are not configured: ${missing.join(', ')} `
      + `${missing.length === 1 ? 'is' : 'are'} not set.`,
    '',
    'These scripts sign in to a running development server. They no longer',
    'carry a built-in username and password, so the account has to be named',
    'explicitly. Set both variables and re-run:',
    '',
    '  PowerShell:',
    `    $env:${USER_VAR} = 'walkthrough_user'`,
    `    $env:${PASS_VAR} = '<the account password>'`,
    '',
    '  bash / zsh:',
    `    export ${USER_VAR}=walkthrough_user`,
    `    export ${PASS_VAR}='<the account password>'`,
    '',
    'If the account does not exist yet, create one against the development',
    'database with:',
    '',
    '    python nanobio_studio_backend/scripts/create_admin.py --username '
      + 'walkthrough_user',
    '',
    'Nothing was run and no browser was launched.',
    '',
  ].join('\n');
}

/**
 * Return `{ user, pass }` or exit non-zero with an explanation.
 *
 * Exits rather than throwing: these are top-level scripts, and a thrown error
 * here would be reported as an unhandled rejection with a stack trace, burying
 * the one line the operator needs.
 */
export function walkthroughCredentials() {
  const user = process.env[USER_VAR];
  const pass = process.env[PASS_VAR];

  const missing = [];
  if (!user || !user.trim()) missing.push(USER_VAR);
  if (!pass || !pass.trim()) missing.push(PASS_VAR);

  if (missing.length) {
    console.error(guidance(missing));
    process.exit(2);
  }
  return { user: user.trim(), pass };
}
