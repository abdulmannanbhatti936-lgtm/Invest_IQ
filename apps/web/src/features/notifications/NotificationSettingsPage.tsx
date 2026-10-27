import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { BellOff } from 'lucide-react';
import { getErrorDetail } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { NotificationPreferencesUpdate, NotificationType } from '@investiq/shared-types';
import { Button } from '../../components/ui/Button';
import { Card, CardTitle } from '../../components/ui/Card';
import { ErrorState, Notice, Skeleton } from '../../components/ui/Feedback';
import { Input } from '../../components/ui/Input';
import { PageHeader } from '../../components/ui/PageHeader';
import { Select } from '../../components/ui/Select';
import { Switch } from '../../components/ui/Switch';
import {
  EVERYTHING_OFF,
  MAX_DAILY_CAP,
  TYPE_ORDER,
  editable,
  quietHoursValid,
} from './notificationView';
import { useNotificationPreferences, useUpdatePreferences } from './useNotifications';
import {
  WebPushError,
  disableWebPush,
  enableWebPush,
  thisBrowserRegistered,
  webPushConfigured,
  type PushProblem,
} from './webPush';

const PUSH_PROBLEM_KEY: Record<PushProblem, string> = {
  not_configured: 'notifications.settings.pushUnavailable',
  unsupported: 'notifications.settings.pushUnsupported',
  blocked: 'notifications.settings.pushBlocked',
  failed: 'notifications.settings.pushError',
};

const Section = ({ title, children }: { title: string; children: ReactNode }) => (
  <Card className="space-y-4">
    <CardTitle>{title}</CardTitle>
    {children}
  </Card>
);

export const NotificationSettingsPage = () => {
  const { t, i18n } = useTranslation();
  const prefs = useNotificationPreferences();
  const save = useUpdatePreferences();
  const pushSave = useUpdatePreferences();
  const [form, setForm] = useState<NotificationPreferencesUpdate | null>(null);
  const [saved, setSaved] = useState<'settings' | 'off' | null>(null);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushProblem, setPushProblem] = useState<PushProblem | null>(null);
  const language = i18n.language.startsWith('ur') ? 'ur' : 'en';

  useEffect(() => {
    if (prefs.data && form === null) setForm(editable(prefs.data));
  }, [prefs.data, form]);

  if (prefs.isPending || (prefs.data && form === null)) {
    return (
      <div className="space-y-6" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (prefs.isError || !form) {
    return (
      <ErrorState message={t('notifications.settings.loadError')} onRetry={() => prefs.refetch()} />
    );
  }

  const current = prefs.data;
  const update = (changes: NotificationPreferencesUpdate) => {
    setSaved(null);
    setForm({ ...form, ...changes });
  };
  const quietOk = quietHoursValid(form);
  const serverQuietError = getErrorDetail(save.error)?.code === 'quiet_hours_empty';

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!quietOk) return;
    save.mutate({ ...form, language }, { onSuccess: () => setSaved('settings') });
  };

  const pushAvailable = current.push_available && webPushConfigured();
  const pushOn = current.push_enabled && thisBrowserRegistered();
  const togglePush = async (on: boolean) => {
    setPushProblem(null);
    setPushBusy(true);
    try {
      if (on) await enableWebPush();
      else await disableWebPush();
      await pushSave.mutateAsync({ push_enabled: on, language });
    } catch (error) {
      setPushProblem(error instanceof WebPushError ? error.problem : 'failed');
    } finally {
      setPushBusy(false);
    }
  };

  const turnEverythingOff = async () => {
    setPushProblem(null);
    await disableWebPush();
    pushSave.mutate(EVERYTHING_OFF, {
      onSuccess: (next) => {
        setForm(editable(next));
        setSaved('off');
      },
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('notifications.settings.title')}
        subtitle={t('notifications.settings.subtitle')}
        back={{ to: '/notifications', label: t('notifications.title') }}
      />

      <form className="space-y-6" onSubmit={submit} noValidate>
        <Section title={t('notifications.settings.typesTitle')}>
          <div className="divide-y divide-line">
            {TYPE_ORDER.map((type: NotificationType) => {
              const key = `${type}_enabled` as const;
              return (
                <Switch
                  key={type}
                  label={t(`notifications.settings.types.${type}.label`)}
                  help={t(`notifications.settings.types.${type}.help`)}
                  checked={Boolean(form[key])}
                  onChange={(checked) => update({ [key]: checked })}
                />
              );
            })}
          </div>
        </Section>

        <Section title={t('notifications.settings.sensitivityTitle')}>
          <fieldset className="space-y-2">
            <legend className="sr-only">{t('notifications.settings.sensitivityTitle')}</legend>
            {(['all', 'strong_only'] as const).map((option) => (
              <label key={option} className="flex min-h-10 items-center gap-4 text-sm text-ink">
                <input
                  type="radio"
                  name="sensitivity"
                  value={option}
                  checked={form.sensitivity === option}
                  onChange={() => update({ sensitivity: option })}
                  className="h-4 w-4 accent-primary"
                />
                {t(`notifications.settings.sensitivity.${option}`)}
              </label>
            ))}
          </fieldset>
          <Notice>{t('notifications.settings.strongOnlyNote')}</Notice>
        </Section>

        <Section title={t('notifications.settings.capTitle')}>
          <div className="max-w-xs">
            <Select
              label={t('notifications.settings.capLabel')}
              value={form.daily_cap}
              onChange={(e) => update({ daily_cap: Number(e.target.value) })}
            >
              {Array.from({ length: MAX_DAILY_CAP }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Select>
          </div>
          <p className="text-sm text-muted">{t('notifications.settings.capHelp')}</p>
        </Section>

        <Section title={t('notifications.settings.quietTitle')}>
          <Switch
            label={t('notifications.settings.quietToggle')}
            help={t('notifications.settings.quietHelp')}
            checked={Boolean(form.quiet_hours_enabled)}
            onChange={(checked) => update({ quiet_hours_enabled: checked })}
          />
          {form.quiet_hours_enabled && (
            <div className="grid max-w-md grid-cols-2 gap-4">
              <Input
                type="time"
                dir="ltr"
                label={t('notifications.settings.quietStart')}
                value={form.quiet_start ?? ''}
                onChange={(e) => update({ quiet_start: e.target.value })}
                error={
                  quietOk && !serverQuietError ? undefined : t('notifications.settings.quietSame')
                }
              />
              <Input
                type="time"
                dir="ltr"
                label={t('notifications.settings.quietEnd')}
                value={form.quiet_end ?? ''}
                onChange={(e) => update({ quiet_end: e.target.value })}
              />
            </div>
          )}
        </Section>

        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" isLoading={save.isPending} disabled={!quietOk}>
            {t('notifications.settings.save')}
          </Button>
          {saved === 'settings' && (
            <p role="status" className="text-sm text-success">
              {t('notifications.settings.saved')}
            </p>
          )}
          {save.isError && !serverQuietError && (
            <p role="alert" className="text-sm text-danger">
              {t('notifications.settings.error')}
            </p>
          )}
        </div>
      </form>

      <Section title={t('notifications.settings.pushTitle')}>
        <Switch
          label={t('notifications.settings.pushToggle')}
          checked={pushOn}
          disabled={!pushAvailable || pushBusy}
          onChange={(checked) => void togglePush(checked)}
        />
        {!pushAvailable && <Notice>{t('notifications.settings.pushUnavailable')}</Notice>}
        {pushProblem && <Notice tone="warning">{t(PUSH_PROBLEM_KEY[pushProblem])}</Notice>}
      </Section>

      <Section title={t('notifications.settings.offTitle')}>
        <p className="text-sm text-muted">{t('notifications.settings.offBody')}</p>
        <div className="flex flex-wrap items-center gap-4">
          <Button
            variant="destructive"
            isLoading={pushSave.isPending}
            onClick={() => void turnEverythingOff()}
          >
            <BellOff className="h-4 w-4" aria-hidden="true" />
            {t('notifications.settings.offButton')}
          </Button>
          {saved === 'off' && (
            <p role="status" className="text-sm text-success">
              {t('notifications.settings.offDone')}
            </p>
          )}
        </div>
      </Section>
    </div>
  );
};
