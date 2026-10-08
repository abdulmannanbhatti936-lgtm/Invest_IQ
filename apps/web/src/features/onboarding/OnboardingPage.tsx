import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Check, LogOut } from 'lucide-react';
import { riskProfileApi } from '@investiq/api-client';
import { useTranslation } from '@investiq/i18n';
import type { OnboardingProgress, RiskAnswers, RiskProfile } from '@investiq/shared-types';
import { useAuth } from '../auth/AuthContext';
import { onboardingRedirect, RETAKE_PARAM } from '../auth/guardRules';
import { Button } from '../../components/ui/Button';
import { DisclaimerBanner, ErrorState, Notice, Skeleton } from '../../components/ui/Feedback';
import { LanguageToggle } from '../../components/LanguageToggle';
import { RiskBadge } from './RiskBadge';
import { createLatestOnlySender } from '../../lib/latestOnlySender';

export const OnboardingPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [searchParams] = useSearchParams();
  const isRetake = !!user?.has_risk_profile && searchParams.get(RETAKE_PARAM) === '1';
  const queryClient = useQueryClient();

  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<RiskAnswers>({});
  const [restored, setRestored] = useState(false);
  const [resumed, setResumed] = useState(false);
  const [result, setResult] = useState<RiskProfile | null>(null);

  // A completed profile only reopens the questionnaire as an explicit retake (FR5)
  const redirect = onboardingRedirect(user, {
    retake: searchParams.get(RETAKE_PARAM) === '1',
    showingResult: result !== null,
  });

  // The question set is defined once, on the server; labels come from i18n by id
  const questionnaire = useQuery({
    queryKey: ['risk-questionnaire'],
    queryFn: riskProfileApi.getQuestionnaire,
    staleTime: Infinity,
    retry: 1,
    enabled: !redirect,
  });
  const questions = questionnaire.data ?? [];
  const total = questions.length;

  // FR6: pick up where the user left off
  const progress = useQuery({
    queryKey: ['onboarding-progress'],
    queryFn: riskProfileApi.getProgress,
    staleTime: Infinity,
    retry: 1,
    enabled: !redirect,
  });

  useEffect(() => {
    // Never start over while the saved draft couldn't be read: the next answer would overwrite it
    if (restored || progress.isPending || progress.isError || !questionnaire.data) return;
    const saved = progress.data;
    if (saved && Object.keys(saved.answers).length > 0) {
      setAnswers(saved.answers);
      setStep(Math.min(saved.current_step, questionnaire.data.length - 1));
      setResumed(true);
    }
    setRestored(true);
  }, [progress.isPending, progress.isError, progress.data, questionnaire.data, restored]);

  // Draft saves go out one at a time, latest answers last, so the server never keeps an
  // older step than the user reached (FR6 resume)
  const [draftSaveFailed, setDraftSaveFailed] = useState(false);
  const [draftSender] = useState(() =>
    createLatestOnlySender<OnboardingProgress>(riskProfileApi.saveProgress, (ok) =>
      setDraftSaveFailed(!ok),
    ),
  );
  const saveProfile = useMutation({
    mutationFn: async (final: RiskAnswers) => {
      // Let any in-flight draft finish first: a late draft save would re-create the draft
      // the server clears when the profile is saved
      await draftSender.flush();
      return riskProfileApi.save(final);
    },
    onSuccess: async (profile) => {
      // The server clears the draft once the profile is saved
      queryClient.removeQueries({ queryKey: ['onboarding-progress'] });
      queryClient.setQueryData(['risk-profile'], profile);
      // Show the result before the user refresh marks the profile complete, so the
      // onboarding guard keeps this screen instead of redirecting to the dashboard
      setResult(profile);
      await refreshUser();
    },
  });

  const question = questions[step];

  const choose = (value: string) => {
    const next = { ...answers, [question.id]: value };
    setAnswers(next);
    if (step < total - 1) {
      setStep(step + 1);
      draftSender.send({ answers: next, current_step: step + 1 });
    } else {
      saveProfile.mutate(next);
    }
  };

  const goBack = () => {
    if (step === 0) return;
    setStep(step - 1);
    draftSender.send({ answers, current_step: step - 1 });
  };

  if (redirect) return <Navigate to={redirect} replace />;

  if (result) {
    return (
      <Shell>
        <div className="space-y-6 rounded-xl border border-gray-100 bg-white p-8 text-center shadow-sm">
          <RiskBadge category={result.category} size="lg" />
          <h1 className="text-2xl font-bold text-gray-900">
            {t('onboarding.result.title', { category: t(`risk.${result.category}`) })}
          </h1>
          <p className="leading-relaxed text-gray-600">
            {t(`risk.description.${result.category}`)}
          </p>
          {result.caps_applied.length > 0 && (
            // Explain in plain language why the profile is lower than the score alone suggests
            <div className="space-y-2 text-start">
              {result.caps_applied.map((cap) => (
                <Notice key={cap}>{t(`onboarding.result.caps.${cap}`)}</Notice>
              ))}
            </div>
          )}
          <Button className="w-full" onClick={() => navigate('/dashboard', { replace: true })}>
            {t('onboarding.result.cta')}
          </Button>
        </div>
      </Shell>
    );
  }

  if (progress.isError || questionnaire.isError || (restored && !question)) {
    return (
      <Shell>
        <ErrorState
          message={t('onboarding.loadError')}
          onRetry={() => {
            if (progress.isError) void progress.refetch();
            if (questionnaire.isError) void questionnaire.refetch();
          }}
        />
      </Shell>
    );
  }

  if (!restored) {
    return (
      <Shell>
        <Skeleton className="mb-6 h-2 w-full" />
        <Skeleton className="mb-8 h-8 w-3/4" />
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="mb-3 h-16 w-full" />
        ))}
      </Shell>
    );
  }

  const progressPct = ((step + 1) / total) * 100;
  const prefix = `onboarding.questions.${question.id}`;

  return (
    <Shell>
      <div className="mb-8">
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-gray-200"
          role="progressbar"
          aria-valuemin={1}
          aria-valuemax={total}
          aria-valuenow={step + 1}
        >
          <div
            className="h-full bg-blue-600 transition-all duration-300 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <p className="mt-2 text-end text-xs font-medium tracking-wider text-gray-500 uppercase">
          {t('onboarding.stepOf', { current: step + 1, total })}
        </p>
      </div>

      {draftSaveFailed && (
        // Non-blocking: answers stay on the page and the next answer re-sends all of them
        <div className="mb-6" role="status">
          <Notice tone="warning">{t('onboarding.draftSaveError')}</Notice>
        </div>
      )}

      {resumed && step > 0 && (
        <div className="mb-6">
          <Notice>{t('onboarding.resumed')}</Notice>
        </div>
      )}

      <h1 className="text-2xl leading-tight font-bold text-gray-900">{t(`${prefix}.title`)}</h1>

      <div className="mt-8 space-y-3">
        {question.options.map((option) => {
          const selected = answers[question.id] === option;
          return (
            <button
              key={option}
              type="button"
              onClick={() => choose(option)}
              disabled={saveProfile.isPending}
              aria-pressed={selected}
              className={`group flex w-full items-center rounded-xl border-2 bg-white p-4 text-start transition-colors duration-200 hover:border-blue-500 hover:bg-blue-50 focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:opacity-50 ${
                selected ? 'border-blue-500 bg-blue-50' : 'border-gray-100'
              }`}
            >
              <span
                className={`me-4 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
                  selected
                    ? 'border-blue-600 bg-blue-600'
                    : 'border-gray-300 group-hover:border-blue-500'
                }`}
              >
                {selected && <Check className="h-4 w-4 text-white" />}
              </span>
              <span className="font-medium text-gray-700 group-hover:text-gray-900">
                {t(`${prefix}.options.${option}`)}
              </span>
            </button>
          );
        })}
      </div>

      {saveProfile.isError && (
        <div className="mt-6">
          <ErrorState
            message={t('onboarding.saveError')}
            onRetry={() => saveProfile.mutate(answers)}
          />
        </div>
      )}

      <div className="mt-10 flex h-10 items-center justify-between">
        {step > 0 ? (
          <button
            type="button"
            onClick={goBack}
            className="flex items-center gap-1 text-sm font-medium text-gray-500 transition-colors hover:text-gray-900"
          >
            <ArrowLeft className="h-4 w-4 rtl:rotate-180" />
            {t('common.back')}
          </button>
        ) : (
          <span />
        )}
        {saveProfile.isPending ? (
          <span className="animate-pulse text-sm text-gray-500">{t('onboarding.saving')}</span>
        ) : (
          isRetake && (
            // A retake must never trap the user: they keep their current profile if they leave
            <Link
              to="/dashboard"
              className="text-sm font-medium text-gray-500 transition-colors hover:text-gray-900"
            >
              {t('onboarding.cancelRetake')}
            </Link>
          )
        )}
      </div>
    </Shell>
  );
};

const Shell = ({ children }: { children: React.ReactNode }) => {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  // Answers given so far are already saved as a draft, so leaving here loses nothing (FR6)
  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };
  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <header className="flex items-center justify-between px-6 py-4">
        <span className="text-xl font-bold tracking-tight text-blue-700">
          {t('common.appName')}
        </span>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <button
            type="button"
            onClick={handleLogout}
            className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900"
          >
            <LogOut className="h-4 w-4 rtl:rotate-180" />
            {t('common.logout')}
          </button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-lg flex-1 px-4 pt-8 pb-12">
        <p className="mb-6 text-sm font-semibold text-blue-700">{t('onboarding.title')}</p>
        {children}
        <div className="mt-10">
          <DisclaimerBanner />
        </div>
      </main>
    </div>
  );
};
