import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import NotificationCenter from './NotificationCenter';
import * as api from '../../api/notificationClient';

vi.mock('../../api/notificationClient');

const row: api.NotificationRow = {
  id: 17,
  event: 'candidate_revision_created',
  organization_id: 2,
  study_id: 3,
  subject_type: 'candidate',
  subject_id: 4,
  summary: 'A candidate revision was created.',
  created_at: '2026-08-05T09:30:00Z',
  read_at: null,
  is_read: false,
  target_status: 'available',
  href: '/candidates/4/versions',
};

const ok = <T,>(data: T) => ({ status: 'ok' as const, data });

describe('NotificationCenter', () => {
  beforeEach(() => {
    vi.mocked(api.listNotifications).mockResolvedValue(ok({ notifications: [row], unread_count: 1 }));
    vi.mocked(api.markNotificationRead).mockResolvedValue(ok({ id: 17, read_at: '2026-08-05T10:00:00Z', is_read: true }));
    vi.mocked(api.markNotificationsRead).mockResolvedValue(ok({ marked_read_ids: [17], marked_read_count: 1, unread_count: 0 }));
  });

  it('shows safe event context, status, timestamp and authorized link', async () => {
    render(<MemoryRouter><NotificationCenter /></MemoryRouter>);
    expect(await screen.findByText('A candidate revision was created.')).toBeInTheDocument();
    expect(screen.getByText('Unread')).toBeInTheDocument();
    expect(screen.getByRole('time')).toHaveAttribute('datetime', row.created_at);
    expect(screen.getByRole('link', { name: 'Open record' })).toHaveAttribute('href', row.href);
  });

  it('marks all notifications read', async () => {
    render(<MemoryRouter><NotificationCenter /></MemoryRouter>);
    await userEvent.click(await screen.findByRole('button', { name: 'Mark all as read' }));
    expect(api.markNotificationsRead).toHaveBeenCalledWith(null);
  });

  it('renders inaccessible targets without a navigation link', async () => {
    vi.mocked(api.listNotifications).mockResolvedValue(ok({
      notifications: [{ ...row, target_status: 'inaccessible', href: null }], unread_count: 1,
    }));
    render(<MemoryRouter><NotificationCenter /></MemoryRouter>);
    expect(await screen.findByText(/no longer accessible/i)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Open record' })).not.toBeInTheDocument();
  });

  it('renders empty and loading outcomes accessibly', async () => {
    vi.mocked(api.listNotifications).mockResolvedValue(ok({ notifications: [], unread_count: 0 }));
    render(<MemoryRouter><NotificationCenter /></MemoryRouter>);
    expect(await screen.findByText('No notifications')).toBeInTheDocument();
  });
});
