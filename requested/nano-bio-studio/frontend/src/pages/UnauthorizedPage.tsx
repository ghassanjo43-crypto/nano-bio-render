import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Button, Card, EmptyState } from '../design-system/components';
import { Icon } from '../shell/Icon';

export default function UnauthorizedPage() {
  const { user } = useAuth();
  return (
    <Card className="centred-page">
      <div data-testid="unauthorized">
        <EmptyState
          icon={<Icon name="shield" size={22} />}
          title="Access restricted"
          action={
            <Link to="/dashboard">
              <Button variant="secondary"
                      iconRight={<Icon name="arrow-right" size={15} />}>
                Return to dashboard
              </Button>
            </Link>
          }
        >
          Your account{user ? ` (${user.role})` : ''} does not have permission to
          open this area. If you need access, contact a platform administrator.
        </EmptyState>
      </div>
    </Card>
  );
}
