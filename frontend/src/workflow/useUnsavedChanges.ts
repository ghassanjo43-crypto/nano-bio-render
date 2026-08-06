/**
 * Unsaved-change detection and the guard that acts on it.
 *
 * Why this is hand-rolled
 * -----------------------
 * React Router's `useBlocker` needs a data router (`createBrowserRouter`). This
 * application mounts `<Routes>` inside a plain `<BrowserRouter>`, and the test
 * suite mounts it inside `<MemoryRouter>`, so `useBlocker` is simply not
 * available. Migrating the whole app to a data router to obtain one hook would
 * be a large, risky change to routing that every existing test depends on.
 *
 * So the guard is explicit: navigation that leaves a dirty study goes through
 * `useGuardedNavigate`, which asks first. This is *narrower* than a router-level
 * block — a link that bypasses the hook is not intercepted — and that limit is
 * stated here rather than papered over. The two paths that matter are covered:
 * the pathway controls, and closing or reloading the tab.
 *
 * What counts as "unsaved"
 * ------------------------
 * A comparison of the live session against a snapshot taken at the last save,
 * over the fields the user actually edits. Deliberately not `updatedAt`, which
 * changes on every keystroke and would report a study dirty after a save that
 * changed nothing.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * The subset of a session that constitutes user work.
 *
 * `furthestStep` and `updatedAt` are excluded on purpose: reaching a step is
 * navigation, not data, and treating it as unsaved work would pop a warning at
 * the user for having read a page.
 */
export interface DirtyFingerprint {
  selection: unknown;
  values: unknown;
  chips: unknown;
  pk: unknown;
  name: string;
  projectId: number | null;
  candidateName: string;
}

export function fingerprint(input: DirtyFingerprint): string {
  return JSON.stringify([
    input.selection, input.values, input.chips, input.pk,
    input.name, input.projectId, input.candidateName,
  ]);
}

/**
 * Warn on tab close or reload while work is unsaved.
 *
 * The browser shows its own wording; a custom string has been ignored by every
 * major browser for years. Registering the handler at all is what produces the
 * prompt, so it is attached only while genuinely dirty — an unconditional
 * handler would nag on every navigation away from a clean study.
 */
export function useBeforeUnloadWarning(isDirty: boolean): void {
  useEffect(() => {
    if (!isDirty) return undefined;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // Legacy browsers require returnValue to be set for the prompt to show.
      event.returnValue = '';
      return '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);
}

export interface PendingNavigation {
  to: string;
  /** What the user was trying to do, for the dialog wording. */
  intent: 'back' | 'exit' | 'continue' | 'other';
}

export interface GuardedNavigation {
  /** Non-null while a confirmation is open. */
  pending: PendingNavigation | null;
  /** Navigate, asking first when there is unsaved work. */
  guardedNavigate: (to: string, intent?: PendingNavigation['intent']) => void;
  /** Leave without saving. */
  discardAndGo: () => void;
  /** Save, then leave. */
  saveAndGo: () => void;
  /** Stay where we are. */
  cancel: () => void;
}

/**
 * Build the guard.
 *
 * `onSave` is invoked by `saveAndGo`, so the dialog can offer a way out that
 * does not throw work away. A confirmation whose only options are "lose your
 * changes" and "stay here" trains people to click through it.
 */
export function useGuardedNavigate(
  isDirty: boolean,
  navigate: (to: string) => void,
  onSave: () => void,
): GuardedNavigation {
  const [pending, setPending] = useState<PendingNavigation | null>(null);
  // Read inside callbacks so a stale closure cannot let a dirty study through.
  const dirtyRef = useRef(isDirty);
  dirtyRef.current = isDirty;

  const guardedNavigate = useCallback(
    (to: string, intent: PendingNavigation['intent'] = 'other') => {
      if (!dirtyRef.current) {
        navigate(to);
        return;
      }
      setPending({ to, intent });
    },
    [navigate],
  );

  const discardAndGo = useCallback(() => {
    setPending((current) => {
      if (current) navigate(current.to);
      return null;
    });
  }, [navigate]);

  const saveAndGo = useCallback(() => {
    onSave();
    setPending((current) => {
      if (current) navigate(current.to);
      return null;
    });
  }, [navigate, onSave]);

  const cancel = useCallback(() => setPending(null), []);

  return { pending, guardedNavigate, discardAndGo, saveAndGo, cancel };
}

export const LEAVE_PROMPT = {
  title: 'You have unsaved changes',
  body:
    'This study has changes that are not saved. Leaving now discards them.',
  save: 'Save and continue',
  discard: 'Leave without saving',
  cancel: 'Stay on this page',
} as const;
