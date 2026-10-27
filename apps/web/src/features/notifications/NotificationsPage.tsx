import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BellOff, BellRing, CheckCheck, Settings } from 'lucide-react';
import { getErrorStatus } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { AppNotification } from '@investiq/shared-types';
import { Button, buttonClasses } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { DisclaimerBanner, EmptyState, ErrorState, Skeleton } from '../../components/ui/Feedback';
import { PageHeader } from '../../components/ui/PageHeader';
import { NotificationCard } from './NotificationCard';
import { ALL_TYPES_ON, groupByType, isOptedOut } from './notificationView';
import {
  useMarkAllRead,
  useMarkRead,
  useNotificationList,
  useNotificationPreferences,
  useUpdatePreferences,
} from './useNotifications';

type View = 'newest' | 'byType';
const VIEW_KEY = 'investiq.notifications_view';

const savedView = (): View => {
  try {
    return localStorage.getItem(VIEW_KEY) === 'byType' ? 'byType' : 'newest';
  } catch {
    return 'newest';
  }
};

const ListSkeleton = () => (
  <div className="space-y-4" aria-busy="true">
    {Array.from({ length: 3 }, (_, i) => (
      <Card key={i} className="space-y-4">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-24 w-full" />
      </Card>
    ))}
  </div>
);

export const NotificationsPage = () => {
  const { t } = useTranslation();
  const [view, setView] = useState<View>(savedView);
  const list = useNotificationList();
  const prefs = useNotificationPreferences();
  const turnOn = useUpdatePreferences();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();

  const chooseView = (next: View) => {
    setView(next);
    try {
      localStorage.setItem(VIEW_KEY, next);
    } catch {
      // A remembered view is a convenience only
    }
  };

  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const unread = list.data?.pages[0]?.unread_count ?? 0;
  const open = (n: AppNotification) => {
    if (!n.read) markRead.mutate(n.id);
  };
  const card = (n: AppNotification) => (
    <li key={n.id}>
      <NotificationCard
        n={n}
        onOpen={open}
        onMarkRead={(item) => markRead.mutate(item.id)}
        marking={markRead.isPending && markRead.variables === n.id}
      />
    </li>
  );

  const content = () => {
    if (list.isPending || prefs.isPending) return <ListSkeleton />;
    if (list.isError || prefs.isError) {
      const limited = getErrorStatus(list.error ?? prefs.error) === 429;
      return (
        <ErrorState
          message={t(limited ? 'notifications.rateLimited' : 'notifications.error')}
          onRetry={() => {
            void list.refetch();
            void prefs.refetch();
          }}
        />
      );
    }
    if (items.length === 0) {
      const off = isOptedOut(prefs.data);
      return (
        <Card>
          <EmptyState
            icon={off ? BellOff : BellRing}
            title={t(off ? 'notifications.empty.offTitle' : 'notifications.empty.title')}
            action={
              off ? (
                <div className="flex flex-wrap justify-center gap-2">
                  <Button isLoading={turnOn.isPending} onClick={() => turnOn.mutate(ALL_TYPES_ON)}>
                    {t('notifications.bell.optIn.button')}
                  </Button>
                  <Link to="/notifications/settings" className={buttonClasses('secondary')}>
                    {t('notifications.bell.optIn.settings')}
                  </Link>
                </div>
              ) : undefined
            }
          >
            {t(off ? 'notifications.empty.offBody' : 'notifications.empty.body')}
          </EmptyState>
        </Card>
      );
    }
    return (
      <div className="space-y-6">
        {view === 'newest' ? (
          <ul className="space-y-4">{items.map(card)}</ul>
        ) : (
          groupByType(items).map((group) => (
            <section key={group.type} className="space-y-4" aria-labelledby={`group-${group.type}`}>
              <h2 id={`group-${group.type}`} className="text-lg font-semibold text-ink">
                {t(`notifications.type.${group.type}`)}
              </h2>
              <ul className="space-y-4">{group.items.map(card)}</ul>
            </section>
          ))
        )}
        {list.hasNextPage && (
          <div className="flex justify-center">
            <Button
              variant="secondary"
              isLoading={list.isFetchingNextPage}
              onClick={() => void list.fetchNextPage()}
            >
              {t('notifications.loadMore')}
            </Button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('notifications.title')}
        subtitle={t('notifications.subtitle')}
        actions={
          <>
            {unread > 0 && (
              <Button
                variant="secondary"
                isLoading={markAllRead.isPending}
                onClick={() => markAllRead.mutate()}
              >
                <CheckCheck className="h-4 w-4" aria-hidden="true" />
                {t('notifications.markAllRead')}
              </Button>
            )}
            <Link to="/notifications/settings" className={buttonClasses('secondary')}>
              <Settings className="h-4 w-4" aria-hidden="true" />
              {t('notifications.settingsLink')}
            </Link>
          </>
        }
      />

      {items.length > 0 && (
        <div
          role="radiogroup"
          aria-label={t('notifications.view.label')}
          className="inline-flex rounded-control border border-line bg-sunken p-2"
        >
          {(['newest', 'byType'] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={view === option}
              onClick={() => chooseView(option)}
              className={`min-h-8 rounded-control px-4 text-sm font-medium transition-colors ${
                view === option ? 'bg-surface text-ink shadow-e1' : 'text-muted hover:text-ink'
              }`}
            >
              {t(`notifications.view.${option}`)}
            </button>
          ))}
        </div>
      )}

      {content()}
      <DisclaimerBanner />
    </div>
  );
};
