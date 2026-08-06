import { Link } from 'react-router-dom';
import { Button, Card, EmptyState } from '../design-system/components';
import { Icon } from '../shell/Icon';

export default function NotFoundPage() {
  return (
    <Card className="centred-page">
      <div data-testid="not-found">
        <EmptyState
          icon={<Icon name="info" size={22} />}
          title="Page not found"
          action={
            <Link to="/dashboard">
              <Button iconRight={<Icon name="arrow-right" size={15} />}>
                Return to dashboard
              </Button>
            </Link>
          }
        >
          The page you requested does not exist, or has moved during the
          platform migration.
        </EmptyState>
      </div>
    </Card>
  );
}
