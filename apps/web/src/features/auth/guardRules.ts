// Route-guard decisions as pure functions, so every rule is unit-testable without a browser.
// Each returns the path to redirect to, or null to let the user through. `user` always comes
// from the server's /users/me response — never from anything stored on the client.
// Structurally the two fields of the shared `User` type that the guards need (kept local so
// this module stays importable by Node's test runner without the workspace package).
type GuardUser = { has_risk_profile: boolean; role: 'user' | 'admin' } | null;

/** Query flag that marks a deliberate retake of the questionnaire (FR5). */
export const RETAKE_PARAM = 'retake';
export const RETAKE_PATH = `/onboarding?${RETAKE_PARAM}=1`;

/** Dashboard, stocks, portfolio, … : login first, then a completed risk profile (PRD §7.1). */
export const protectedRouteRedirect = (user: GuardUser): string | null => {
  if (!user) return '/login';
  if (!user.has_risk_profile) return '/onboarding';
  return null;
};

/** The questionnaire: open until the profile exists, afterwards only as a retake. */
export const onboardingRedirect = (
  user: GuardUser,
  { retake, showingResult }: { retake: boolean; showingResult: boolean },
): string | null => {
  if (!user) return '/login';
  if (user.has_risk_profile && !retake && !showingResult) return '/dashboard';
  return null;
};

/** Admin screens (the API must enforce this too). */
export const adminRedirect = (user: GuardUser): string | null =>
  user?.role === 'admin' ? null : '/dashboard';

/**
 * Login/register when already logged in: back to the page originally asked for (only if the
 * profile is complete), otherwise the default landing page.
 */
export const guestRedirect = (user: GuardUser, requestedPath?: string | null): string | null => {
  if (!user) return null;
  if (!user.has_risk_profile) return '/onboarding';
  return safeReturnPath(requestedPath) ?? '/dashboard';
};

/** Only same-app paths; never back to auth/onboarding screens or another site ("//evil.com"). */
export const safeReturnPath = (path?: string | null): string | null => {
  if (!path || !path.startsWith('/') || path.startsWith('//')) return null;
  if (/^\/(login|register|onboarding)(\/|\?|$)/.test(path)) return null;
  return path;
};
