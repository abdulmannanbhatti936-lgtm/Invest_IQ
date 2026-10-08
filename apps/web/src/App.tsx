import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './features/auth/AuthContext';
import {
  GuestOnly,
  RequireAdmin,
  RequireAuth,
  RequireRiskProfile,
} from './features/auth/RouteGuards';
import { LoginPage } from './features/auth/LoginPage';
import { RegisterPage } from './features/auth/RegisterPage';
import { OnboardingPage } from './features/onboarding/OnboardingPage';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { StocksPage } from './features/stocks/StocksPage';
import { StockDetailPage } from './features/stocks/StockDetailPage';
import { ComingSoonPage } from './features/common/ComingSoonPage';
import { AppLayout } from './components/layout/AppLayout';

/** Logged in + completed risk profile + app chrome. */
const AppPage = ({ children }: { children: ReactNode }) => (
  <RequireAuth>
    <RequireRiskProfile>
      <AppLayout>{children}</AppLayout>
    </RequireRiskProfile>
  </RequireAuth>
);

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
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

          {/* Later phases (Phases.md) */}
          <Route
            path="/portfolio"
            element={
              <AppPage>
                <ComingSoonPage section="portfolio" phase={5} />
              </AppPage>
            }
          />
          <Route
            path="/backtest"
            element={
              <AppPage>
                <ComingSoonPage section="backtest" phase={6} />
              </AppPage>
            }
          />
          <Route
            path="/notifications"
            element={
              <AppPage>
                <ComingSoonPage section="notifications" phase={7} />
              </AppPage>
            }
          />
          <Route
            path="/chat"
            element={
              <AppPage>
                <ComingSoonPage section="chat" phase={8} />
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
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
