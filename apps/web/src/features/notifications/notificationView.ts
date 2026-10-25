import type {
  AppNotification,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  NotificationType,
} from '@investiq/shared-types';

export const TYPE_ORDER: NotificationType[] = ['roll', 'sell', 'buy'];
export const MAX_DAILY_CAP = 10;

/** Every type starts off (opt-in); the bell then offers one button to switch them all on. */
export const isOptedOut = (prefs: NotificationPreferences): boolean =>
  !prefs.buy_enabled && !prefs.sell_enabled && !prefs.roll_enabled;

export const ALL_TYPES_ON: NotificationPreferencesUpdate = {
  buy_enabled: true,
  sell_enabled: true,
  roll_enabled: true,
};

/** The unsubscribe: every type and the browser push off; existing notes stay. */
export const EVERYTHING_OFF: NotificationPreferencesUpdate = {
  buy_enabled: false,
  sell_enabled: false,
  roll_enabled: false,
  push_enabled: false,
};

/** The badge on the bell: hidden at zero, "9+" above nine so it stays one pill wide. */
export const unreadBadge = (count: number): string | null =>
  count <= 0 ? null : count > 9 ? '9+' : String(count);

export interface TypeGroup {
  type: NotificationType;
  items: AppNotification[];
}

/** Design.md §7.5 "grouped by type": switches, then sales, then unused cash, newest first. */
export const groupByType = (items: AppNotification[]): TypeGroup[] =>
  TYPE_ORDER.map((type) => ({ type, items: items.filter((n) => n.type === type) })).filter(
    (group) => group.items.length > 0,
  );

/** "22:00:00" from the API to "22:00" for a time input, and back is accepted as is. */
export const toTimeInput = (value: string): string => value.slice(0, 5);

/** Whether a notification rests on a low-confidence forecast (shown with the warning pill). */
export const isLowConfidence = (notification: AppNotification): boolean => {
  if (notification.rule === 'sell_forecast') {
    return notification.params.low_confidence_reasons.length > 0;
  }
  if (notification.rule === 'roll_suggested') {
    const { low_confidence_reasons: held, replacement_low_confidence_reasons: other } =
      notification.params;
    return held == null || other == null || held.length > 0 || other.length > 0;
  }
  return false;
};

/** The settings fields the form edits; anything else in the response is read-only. */
export const editable = (prefs: NotificationPreferences): NotificationPreferencesUpdate => ({
  buy_enabled: prefs.buy_enabled,
  sell_enabled: prefs.sell_enabled,
  roll_enabled: prefs.roll_enabled,
  sensitivity: prefs.sensitivity,
  daily_cap: prefs.daily_cap,
  quiet_hours_enabled: prefs.quiet_hours_enabled,
  quiet_start: toTimeInput(prefs.quiet_start),
  quiet_end: toTimeInput(prefs.quiet_end),
});

export const quietHoursValid = (form: NotificationPreferencesUpdate): boolean =>
  !form.quiet_hours_enabled || form.quiet_start !== form.quiet_end;
