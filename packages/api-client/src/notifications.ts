import type {
  AppNotification,
  NotificationPage,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  PushDevice,
} from '@investiq/shared-types';
import { apiClient } from './client';

export const notificationsApi = {
  /** The user's notifications, newest first, with the unread count; `before` pages back. */
  list: async (before?: string | null, limit = 20): Promise<NotificationPage> => {
    const { data } = await apiClient.get<NotificationPage>('/notifications', {
      params: { limit, ...(before ? { before } : {}) },
    });
    return data;
  },

  markRead: async (id: string): Promise<AppNotification> => {
    const { data } = await apiClient.patch<AppNotification>(`/notifications/${id}/read`);
    return data;
  },

  markAllRead: async (): Promise<{ updated: number }> => {
    const { data } = await apiClient.post<{ updated: number }>('/notifications/read-all');
    return data;
  },

  preferences: async (): Promise<NotificationPreferences> => {
    const { data } = await apiClient.get<NotificationPreferences>('/notifications/preferences');
    return data;
  },

  /** Changes only the fields sent. */
  updatePreferences: async (
    changes: NotificationPreferencesUpdate,
  ): Promise<NotificationPreferences> => {
    const { data } = await apiClient.patch<NotificationPreferences>(
      '/notifications/preferences',
      changes,
    );
    return data;
  },

  registerDevice: async (token: string): Promise<PushDevice> => {
    const { data } = await apiClient.post<PushDevice>('/notifications/devices', {
      platform: 'web',
      token,
    });
    return data;
  },

  removeDevice: async (id: string): Promise<void> => {
    await apiClient.delete(`/notifications/devices/${id}`);
  },
};
