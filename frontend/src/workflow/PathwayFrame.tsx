/**
 * Route-level wrapper that puts the pathway banner, progress and controls
 * around a page without editing the page.
 *
 * Used for the pathway steps that are ordinary modules in their own right —
 * Scientific Readiness, Evidence, Compare, the Protocol and Planning
 * placeholders, the report assessment and the demo workspace. Those pages are
 * reachable from the menu as standalone tools *and* appear as steps on a
 * pathway, and they must behave identically either way.
 *
 * Wrapping rather than editing matters for a specific reason: it keeps the
 * pathway a layer *over* the modules instead of something baked into them. A
 * page that had pathway controls compiled in would carry a study workflow into
 * contexts where no study is open — and would need every one of its existing
 * tests rewritten to accommodate chrome that has nothing to do with what the
 * page does.
 *
 * When no study is open, or the page is not on the current pathway, the
 * controls render nothing and the page appears exactly as it always has.
 */

import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useWorkflow } from './WorkflowContext';
import PathwayNav, { PathwayProgress } from './PathwayNav';
import PathwayBanner from './PathwayBanner';
import { progressFor } from './pathways';

export default function PathwayFrame({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { session, hasResumableSession } = useWorkflow();

  // No study, no pathway. Showing "step 7 of 12" to somebody who opened
  // Evidence from the menu with nothing in progress would be a claim about a
  // study that does not exist.
  const active = hasResumableSession
    && progressFor(session.pathway, pathname).onPathway;

  if (!active) return <>{children}</>;

  return (
    <div data-testid="pathway-frame">
      <PathwayBanner />
      <PathwayProgress />
      {children}
      <PathwayNav />
    </div>
  );
}
