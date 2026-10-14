import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './features/auth/AuthContext';
import {
  FullPageSpinner,
  GuestOnly,
  LandingGate,
  RequireAdmin,
  RequireAuth,
  RequireRiskProfile,
} from './features/auth/RouteGuards';
import { AppLayout } from './components/layout/AppLayout';

// Every screen is its own chunk, so a visitor to the landing page or the login screen never
// downloads the charts, the portfolio screens or three.js (UI round, 2026-10-15).
const named = <K extends string>(load: () => Promise<Record<K, React.ComponentType>>, key: K) =>
  lazy(() => load().then((m) => ({ default: m[key] })));

const LandingPage = named(() => import('./features/landing/LandingPage'), 'LandingPage');
const LoginPage = named(() => import('./features/auth/LoginPage'), 'LoginPage');
const RegisterPage = named(() => import('./features/auth/RegisterPage'), 'RegisterPage');
const OnboardingPage = named(
  () => import('./features/onboarding/OnboardingPage'),
  'OnboardingPage',
);
const DashboardPage = named(() => import('./features/dashboard/DashboardPage'), 'DashboardPage');
const StocksPage = named(() => import('./features/stocks/StocksPage'), 'StocksPage');
const StockDetailPage = named(() => import('./features/stocks/StockDetailPage'), 'StockDetailPage');
const PortfolioPage = named(() => import('./features/portfolio/PortfolioPage'), 'PortfolioPage');
const BacktestPage = named(() => import('./features/backtest/BacktestPage'), 'BacktestPage');
const BacktestReportPage = named(
  () => import('./features/backtest/BacktestReportPage'),
  'BacktestReportPage',
);
const ChatPage = named(() => import('./features/chat/ChatPage'), 'ChatPage');
const ComingSoonPage = lazy(() =>
  import('./features/common/ComingSoonPage').then((m) => ({ default: m.ComingSoonPage })),
);

/** Logged in + completed risk profile + app chrome. */
const AppPage = ({ children }: { children: ReactNode }) => (
  <RequireAuth>
    <RequireRiskProfile>
      <AppLayout>
        <Suspense fallback={null}>{children}</Suspense>
      </AppLayout>
    </RequireRiskProfile>
  </RequireAuth>
);

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<FullPageSpinner />}>
          <Routes>
            <Route
              path="/"
              element={
                <LandingGate>
                  <LandingPage />
                </LandingGate>
              }
            />
            <Route
              path="/login"
              element={
                <GuestOnly>
                  <LoginPage />
                </GuestOnly>
              }
            />
            <Route
              path="/register"
              element={
                <GuestOnly>
                  <RegisterPage />
                </GuestOnly>
              }
            />
            <Route
              path="/onboarding"
              element={
                <RequireAuth>
                  <OnboardingPage />
                </RequireAuth>
              }
            />

            <Route
              path="/dashboard"
              element={
                <AppPage>
                  <DashboardPage />
                </AppPage>
              }
            />
            <Route
              path="/stocks"
              element={
                <AppPage>
                  <StocksPage />
                </AppPage>
              }
            />
            <Route
              path="/stocks/:ticker"
              element={
                <AppPage>
                  <StockDetailPage />
                </AppPage>
              }
            />
            <Route
              path="/portfolio"
              element={
                <AppPage>
                  <PortfolioPage />
                </AppPage>
              }
            />
            <Route
              path="/backtest"
              element={
                <AppPage>
                  <BacktestPage />
                </AppPage>
              }
            />
            <Route
              path="/backtest/:id"
              element={
                <AppPage>
                  <BacktestReportPage />
                </AppPage>
              }
            />
            <Route
              path="/chat"
              element={
                <AppPage>
                  <ChatPage />
                </AppPage>
              }
            />

            {/* Later phases (Phases.md) */}
            <Route
              path="/notifications"
              element={
                <AppPage>
                  <ComingSoonPage section="notifications" phase={7} />
                </AppPage>
              }
            />
            <Route
              path="/admin"
              element={
                <AppPage>
                  <RequireAdmin>
                    <ComingSoonPage section="admin" phase={9} />
                  </RequireAdmin>
                </AppPage>
              }
            />

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
