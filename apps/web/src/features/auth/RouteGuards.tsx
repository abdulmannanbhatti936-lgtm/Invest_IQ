import type { ReactNode } from 'react';
import { Navigate, useLocation, type Location } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { useAuth } from './AuthContext';
import { ErrorState } from '../../components/ui/Feedback';
import {
  adminRedirect,
  guestRedirect,
  landingRedirect,
  protectedRouteRedirect,
} from './guardRules';

export const FullPageSpinner = () => {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg" role="status">
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden="true" />
      <span className="sr-only">{t('common.loading')}</span>
    </div>
  );
};

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
  const redirect = user ? protectedRouteRedirect(user) : null; // RequireAuth handles logged-out
  if (redirect) return <Navigate to={redirect} replace />;
  return <>{children}</>;
};

/** Admin-only screens (Architecture.md §11). The API enforces this too. */
export const RequireAdmin = ({ children }: { children: ReactNode }) => {
  const { user } = useAuth();
  const redirect = adminRedirect(user);
  if (redirect) return <Navigate to={redirect} replace />;
  return <>{children}</>;
};

/**
 * Login/register pages: send already-logged-in users onwards — to the page they originally
 * asked for (RequireAuth passes it as `state.from`) when their profile is complete.
 */
export const GuestOnly = ({ children }: { children: ReactNode }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return <FullPageSpinner />;
  const from = (location.state as { from?: Location } | null)?.from;
  const redirect = guestRedirect(user, from ? from.pathname + from.search : null);
  if (redirect) return <Navigate to={redirect} replace />;
  return <>{children}</>;
};

/** "/": the public landing page for visitors; logged-in users go on to the app. */
export const LandingGate = ({ children }: { children: ReactNode }) => {
  const { user, isLoading } = useAuth();
  if (isLoading) return <FullPageSpinner />;
  const redirect = landingRedirect(user);
  if (redirect) return <Navigate to={redirect} replace />;
  return <>{children}</>;
};
