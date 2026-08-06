import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  listNotifications, markNotificationRead, markNotificationsRead,
  type NotificationRow,
} from '../../api/notificationClient';
import { Alert, Button, EmptyState, SkeletonBlock } from '../../design-system/components';
import './NotificationCenter.css';

const label = (event: string) => event.split('_')
  .map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

const notifyBadge = () => window.dispatchEvent(
  new Event('nanobio:notifications-changed'));

export default function NotificationCenter() {
  const [rows, setRows] = useState<NotificationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await listNotifications();
    setLoading(false);
    if (result.status === 'error') { setError(result.error.message); return; }
    setRows(result.data.notifications); setError(null);
  }, []);
  useEffect(() => { void load(); }, [load]);

  const readOne = async (row: NotificationRow) => {
    if (row.is_read) return;
    const result = await markNotificationRead(row.id);
    if (result.status === 'error') setActionError(result.error.message);
    else notifyBadge();
  };
  const markOne = async (row: NotificationRow) => {
    const result = await markNotificationRead(row.id);
    if (result.status === 'error') { setActionError(result.error.message); return; }
    setActionError(null); notifyBadge(); await load();
  };
  const readAll = async () => {
    const result = await markNotificationsRead(null);
    if (result.status === 'error') { setActionError(result.error.message); return; }
    setActionError(null); notifyBadge(); await load();
  };

  if (loading) return <SkeletonBlock lines={6} />;
  if (error) return <Alert tone="danger" title="Notifications could not be loaded"><p>{error}</p></Alert>;
  if (rows.length === 0) return <EmptyState title="No notifications"><p>Events that need your attention will appear here.</p></EmptyState>;

  return <section className="notifications" aria-labelledby="notifications-title">
    <div className="notifications__head">
      <div><h2 id="notifications-title">Notifications</h2><p>Only events you are authorized to receive are listed.</p></div>
      {rows.some((row) => !row.is_read) && <Button variant="secondary" onClick={() => void readAll()}>Mark all as read</Button>}
    </div>
    {actionError && <Alert tone="danger" title="Notification could not be updated"><p>{actionError}</p></Alert>}
    <ol className="notifications__list">
      {rows.map((row) => <li key={row.id} className={`notification ${row.is_read ? '' : 'notification--unread'}`}>
        <div className="notification__meta">
          <strong>{label(row.event)}</strong>
          <time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time>
          <span>{row.is_read ? 'Read' : 'Unread'}</span>
        </div>
        <p>{row.summary}</p>
        {row.target_status === 'inaccessible' && <p className="notification__stale">The referenced record is no longer accessible.</p>}
        <div className="notification__actions">
          {!row.is_read && <Button variant="secondary" onClick={() => void markOne(row)}>Mark as read</Button>}
          {row.href && <Link to={row.href} onClick={() => void readOne(row)}>Open record</Link>}
        </div>
      </li>)}
    </ol>
  </section>;
}
