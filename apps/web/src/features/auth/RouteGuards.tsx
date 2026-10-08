import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { useAuth } from './AuthContext';
import { ErrorState } from '../../components/ui/Feedback';

const FullPageSpinner = () => (
  <div className="flex min-h-screen items-center justify-center bg-gray-50">
    <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
  </div>
);

/** Logged-in users only; others go to /login and come back afterwards. */
export const RequireAuth = ({ children }: { children: ReactNode }) => {
  const { user, isLoading, loadError, retry } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();

  if (isLoading) return <FullPageSpinner />;
  if (loadError) {
    return (
      <div className="mx-auto mt-24 max-w-md px-4">
        <ErrorState message={t('common.errorGeneric')} onRetry={retry} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
};

/**
 * No dashboard/stocks/portfolio screen without a completed risk profile
 * (PRD.md §7.1 acceptance criteria, Workflow.md Step 1.7).
 */
export const RequireRiskProfile = ({ children }: { children: ReactNode }) => {
  const { user } = useAuth();
  if (user && !user.has_risk_profile) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
};

/** Admin-only screens (Architecture.md §11). The API enforces this too. */
export const RequireAdmin = ({ children }: { children: ReactNode }) => {
  const { user } = useAuth();
  if (user?.role !== 'admin') return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
};

/** Login/register pages: send already-logged-in users onwards. */
export const GuestOnly = ({ children }: { children: ReactNode }) => {
  const { user, isLoading } = useAuth();
  if (isLoading) return <FullPageSpinner />;
  if (user) return <Navigate to={user.has_risk_profile ? '/dashboard' : '/onboarding'} replace />;
  return <>{children}</>;
};
