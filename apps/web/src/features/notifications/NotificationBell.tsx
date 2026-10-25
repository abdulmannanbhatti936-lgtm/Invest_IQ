import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, BellOff } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import type { AppNotification } from '@investiq/shared-types';
import { toggleClasses } from '../../components/LanguageToggle';
import { Button } from '../../components/ui/Button';
import { ErrorState, Skeleton } from '../../components/ui/Feedback';
import { NotificationCard } from './NotificationCard';
import { ALL_TYPES_ON, isOptedOut, unreadBadge } from './notificationView';
import {
  BELL_ITEMS,
  useMarkAllRead,
  useMarkRead,
  useNotificationPreferences,
  useNotificationSummary,
  useRefreshOnPush,
  useUpdatePreferences,
} from './useNotifications';

/**
 * The bell in the header (Design.md §14.1): the unread count, and a panel with the newest few
 * suggestions. While every type is off it offers one button that turns them all on.
 */
export const NotificationBell = () => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const wrapper = useRef<HTMLDivElement>(null);
  const summary = useNotificationSummary();
  const prefs = useNotificationPreferences();
  const turnOn = useUpdatePreferences();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();
  useRefreshOnPush();

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const unread = summary.data?.unread_count ?? 0;
  const badge = unreadBadge(unread);
  const openItem = (n: AppNotification) => {
    if (!n.read) markRead.mutate(n.id);
    setOpen(false);
  };

  const body = () => {
    if (summary.isPending || prefs.isPending) {
      return (
        <div className="space-y-4 p-4" aria-busy="true">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      );
    }
    if (summary.isError || prefs.isError) {
      return (
        <div className="p-4">
          <ErrorState
            message={t('notifications.error')}
            onRetry={() => {
              void summary.refetch();
              void prefs.refetch();
            }}
          />
        </div>
      );
    }
    const items = summary.data.items.slice(0, BELL_ITEMS);
    if (isOptedOut(prefs.data) && items.length === 0) {
      return (
        <div className="space-y-4 p-6 text-center">
          <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-primary-tint text-primary">
            <BellOff className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="space-y-2">
            <p className="font-semibold text-ink">{t('notifications.bell.optIn.title')}</p>
            <p className="text-sm text-muted">{t('notifications.bell.optIn.body')}</p>
          </div>
          {turnOn.isError && (
            <p className="text-sm text-danger">{t('notifications.settings.error')}</p>
          )}
          <div className="flex flex-col items-center gap-2">
            <Button isLoading={turnOn.isPending} onClick={() => turnOn.mutate(ALL_TYPES_ON)}>
              {t('notifications.bell.optIn.button')}
            </Button>
            <Link
              to="/notifications/settings"
              onClick={() => setOpen(false)}
              className="text-sm font-medium text-primary hover:underline"
            >
              {t('notifications.bell.optIn.settings')}
            </Link>
          </div>
        </div>
      );
    }
    if (items.length === 0) {
      return <p className="p-6 text-center text-sm text-muted">{t('notifications.bell.empty')}</p>;
    }
    return (
      <ul className="divide-y divide-line">
        {items.map((n) => (
          <li key={n.id}>
            <NotificationCard n={n} compact onOpen={openItem} />
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div ref={wrapper} className="relative">
      <button
        type="button"
        aria-label={
          unread > 0
            ? t('notifications.bell.labelUnread', { count: unread })
            : t('notifications.bell.label')
        }
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className={`${toggleClasses} relative`}
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {badge && (
          <span
            aria-hidden="true"
            className="absolute -top-2 -end-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-2 text-xs font-bold text-inverse tabular-nums"
          >
            {badge}
          </span>
        )}
      </button>
      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label={t('notifications.title')}
          className="absolute end-0 z-30 mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-card border border-line bg-surface shadow-e3"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2">
            <h2 className="text-sm font-semibold text-ink">{t('notifications.title')}</h2>
            {unread > 0 && (
              <Button
                variant="ghost"
                className="min-h-8 px-2 text-xs"
                isLoading={markAllRead.isPending}
                onClick={() => markAllRead.mutate()}
              >
                {t('notifications.markAllRead')}
              </Button>
            )}
          </div>
          <div className="max-h-[60vh] overflow-y-auto">{body()}</div>
          <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-2 text-sm">
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              className="font-medium text-primary hover:underline"
            >
              {t('notifications.bell.seeAll')}
            </Link>
            <Link
              to="/notifications/settings"
              onClick={() => setOpen(false)}
              className="text-muted hover:text-ink"
            >
              {t('notifications.settingsLink')}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};
