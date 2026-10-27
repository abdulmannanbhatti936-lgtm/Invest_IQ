import { useEffect } from 'react';
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';
import { notificationsApi } from '@investiq/api-client';
import type {
  NotificationPreferences,
  NotificationPreferencesUpdate,
} from '@investiq/shared-types';

export const NOTIFICATIONS_KEY = ['notifications'] as const;
const SUMMARY_KEY = [...NOTIFICATIONS_KEY, 'summary'] as const;
const LIST_KEY = [...NOTIFICATIONS_KEY, 'list'] as const;
const PREFERENCES_KEY = [...NOTIFICATIONS_KEY, 'preferences'] as const;

// The agent writes once a day after the evening forecasts, so a minute's delay is plenty;
// the bell also refreshes when the tab comes back into focus (approved 2026-10-25)
const POLL_MS = 60_000;
export const BELL_ITEMS = 5;
const PAGE_SIZE = 20;

const refreshAll = (client: QueryClient) =>
  client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });

/** The bell: newest few and the unread count. */
export const useNotificationSummary = () =>
  useQuery({
    queryKey: SUMMARY_KEY,
    queryFn: () => notificationsApi.list(null, BELL_ITEMS),
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });

/** The full list, paged back with "Show older". */
export const useNotificationList = () =>
  useInfiniteQuery({
    queryKey: LIST_KEY,
    queryFn: ({ pageParam }) => notificationsApi.list(pageParam, PAGE_SIZE),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_before,
    refetchOnWindowFocus: true,
  });

export const useNotificationPreferences = () =>
  useQuery({ queryKey: PREFERENCES_KEY, queryFn: notificationsApi.preferences });

export const useMarkRead = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => refreshAll(client),
  });
};

export const useMarkAllRead = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => refreshAll(client),
  });
};

export const useUpdatePreferences = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: NotificationPreferencesUpdate) =>
      notificationsApi.updatePreferences(changes),
    onSuccess: (prefs: NotificationPreferences) => {
      client.setQueryData(PREFERENCES_KEY, prefs);
      void refreshAll(client);
    },
  });
};

/**
 * A push that arrives while the app is open (the service worker tells every open tab) refreshes
 * the bell at once instead of at the next poll.
 */
export const useRefreshOnPush = () => {
  const client = useQueryClient();
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === 'investiq-notification') void refreshAll(client);
    };
    navigator.serviceWorker.addEventListener('message', onMessage);
    return () => navigator.serviceWorker.removeEventListener('message', onMessage);
  }, [client]);
};
