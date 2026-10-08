import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Briefcase } from 'lucide-react';
import { riskProfileApi } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import { useAuth } from '../auth/AuthContext';
import { RiskBadge } from '../onboarding/RiskBadge';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { DisclaimerBanner, ErrorState, Skeleton } from '../../components/ui/Feedback';
import { formatDate } from '../../lib/format';

export const DashboardPage = () => {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();

  const profile = useQuery({ queryKey: ['risk-profile'], queryFn: riskProfileApi.get });
  const firstName = user?.full_name.split(' ')[0] ?? '';

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {t('dashboard.welcome', { name: firstName })}
        </h1>
        <p className="mt-1 text-sm text-gray-500">{t('dashboard.subtitle')}</p>
      </div>

      <Card>
        <h2 className="mb-4 text-sm font-semibold tracking-wide text-gray-500 uppercase">
          {t('dashboard.riskTitle')}
        </h2>
        {profile.isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-8 w-40" />
            <Skeleton className="h-4 w-full" />
          </div>
        ) : profile.isError ? (
          <ErrorState message={t('common.errorGeneric')} onRetry={() => void profile.refetch()} />
        ) : (
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="space-y-2">
              <RiskBadge category={profile.data.category} />
              <p className="max-w-2xl text-sm leading-relaxed text-gray-600">
                {t(`risk.description.${profile.data.category}`)}
              </p>
              <p className="text-xs text-gray-400">
                {t('dashboard.updated', {
                  date: formatDate(profile.data.updated_at, i18n.language),
                })}
              </p>
            </div>
            <Button variant="secondary" onClick={() => navigate('/onboarding')}>
              {t('dashboard.retake')}
            </Button>
          </div>
        )}
      </Card>

      {/* Designed empty state (Design.md §12.2); portfolio generation is Phase 5 */}
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white p-12 text-center shadow-sm">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-50">
          <Briefcase className="h-8 w-8 text-blue-600" />
        </div>
        <h3 className="mb-2 text-lg font-semibold text-gray-900">
          {t('dashboard.portfolioEmptyTitle')}
        </h3>
        <p className="mx-auto mb-6 max-w-md text-sm leading-relaxed text-gray-500">
          {t('dashboard.portfolioEmptyBody')}
        </p>
        <Button onClick={() => navigate('/stocks')} className="px-6">
          {t('dashboard.browseStocks')}
        </Button>
      </div>

      <DisclaimerBanner />
    </div>
  );
};
