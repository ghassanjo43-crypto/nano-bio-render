/**
 * Route wrapper: turns the URL parameter into a candidate id.
 *
 * Separate from the page so the page can be rendered in a test with a plain
 * prop, without a router. The alternative — reading `useParams` inside the
 * page — would make every test of the version history also a test of routing,
 * and would make a broken route look like a broken screen.
 */

import { useParams } from 'react-router-dom';
import { Alert } from '../../design-system/components';
import PathwayFrame from '../../workflow/PathwayFrame';
import CandidateVersionsPage from './CandidateVersionsPage';

export default function CandidateVersionsRoute() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const parsed = Number(candidateId);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    return (
      <Alert tone="danger" title="That is not a candidate">
        <p>
          The address does not name a candidate. Open a candidate from the
          registry and choose its version history.
        </p>
      </Alert>
    );
  }

  return (
    <PathwayFrame>
      <CandidateVersionsPage candidateId={parsed} />
    </PathwayFrame>
  );
}
