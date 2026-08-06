/**
 * Route guards.
 *
 * `ProtectedRoute` waits for the initial session check before deciding, so a
 * browser refresh does not briefly bounce an authenticated user to /login.
 */

import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import type { UserRole } from '../api/auth';

function SessionCheck() {
  return (
    <div className="route-checking" role="status" data-testid="session-checking">
      <div className="route-spinner" aria-hidden="true" />
      <p>Restoring session…</p>
    </div>
  );
}

export function ProtectedRoute() {
  const { user, initialising } = useAuth();
  const location = useLocation();

  if (initialising) return <SessionCheck />;
  if (!user) {
    return (
      <Navigate to="/login" replace state={{ from: location.pathname }} />
    );
  }
  return <Outlet />;
}

export function RoleRoute({ roles }: { roles: UserRole[] }) {
  const { user, initialising } = useAuth();
  if (initialising) return <SessionCheck />;
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to="/unauthorized" replace />;
  return <Outlet />;
}
