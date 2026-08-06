import { apiRequest } from './client';

export interface NotificationRow {
  id: number;
  event: string;
  organization_id: number;
  study_id: number | null;
  subject_type: string | null;
  subject_id: number | null;
  summary: string;
  created_at: string;
  read_at: string | null;
  is_read: boolean;
  target_status: 'available' | 'inaccessible' | 'no_link';
  href: string | null;
}

const valid = <T>(key: string) => (body: unknown): body is T =>
  typeof body === 'object' && body !== null && key in body;

export function listNotifications(unreadOnly = false, signal?: AbortSignal) {
  return apiRequest<{ notifications: NotificationRow[]; unread_count: number }>(
    `/api/v1/organizations/notifications/mine?unread_only=${unreadOnly}`,
    { method: 'GET', signal }, valid('notifications'));
}

export function unreadNotificationCount(signal?: AbortSignal) {
  return apiRequest<{ unread_count: number }>(
    '/api/v1/organizations/notifications/unread-count',
    { method: 'GET', signal }, valid('unread_count'));
}

export function markNotificationRead(id: number) {
  return apiRequest<{ id: number; read_at: string; is_read: boolean }>(
    `/api/v1/organizations/notifications/${id}/read`,
    { method: 'POST' }, valid('is_read'));
}

export function markNotificationsRead(ids: number[] | null) {
  return apiRequest<{
    marked_read_ids: number[]; marked_read_count: number; unread_count: number;
  }>('/api/v1/organizations/notifications/mark-read',
    { method: 'POST', body: JSON.stringify({ ids }) }, valid('marked_read_ids'));
}
