import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { healthCheck } from '@investiq/api-client';
import type { Placeholder } from '@investiq/shared-types';
import { colors } from '@investiq/design-tokens';
import i18next from '@investiq/i18n';
import { useEffect, useState } from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Onboarding } from './pages/Onboarding';
import { Dashboard } from './pages/Dashboard';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';

const NavItem = ({ to, label }: { to: string; label: string }) => (
  <Link to={to} className="mx-2 hover:underline">
    {label}
  </Link>
);

const PlaceholderScreen = ({ title }: { title: string }) => {
  const [healthStatus, setHealthStatus] = useState<string>('Loading backend status...');

  useEffect(() => {
    healthCheck()
      .then((res) => setHealthStatus(JSON.stringify(res)))
      .catch((err) => setHealthStatus('Error: ' + err.message));
  }, []);

  return (
    <div className="p-8 text-center" style={{ color: colors.primary }}>
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      <p>{i18next.t('test_key')} (from i18n)</p>
      <p className="mt-4 text-sm text-gray-500">Backend status: {healthStatus}</p>
      <nav className="mt-6">
        <NavItem to="/" label="Home" />
        <NavItem to="/login" label="Login" />
        <NavItem to="/register" label="Register" />
        <NavItem to="/dashboard" label="Dashboard" />
      </nav>
    </div>
  );
};

function App() {
  // Use the imported type just to satisfy TypeScript and test resolution
  const _testType: Placeholder = { id: 'test' };
  console.log(_testType);

  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<PlaceholderScreen title="Home" />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Protected Routes */}
          <Route path="/onboarding" element={
            <ProtectedRoute>
              <Onboarding />
            </ProtectedRoute>
          } />
          
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <AppLayout>
                <Dashboard />
              </AppLayout>
            </ProtectedRoute>
          } />
          <Route path="/stocks" element={
            <ProtectedRoute>
              <AppLayout>
                <PlaceholderScreen title="Stocks" />
              </AppLayout>
            </ProtectedRoute>
          } />
          <Route path="/portfolio" element={
            <ProtectedRoute>
              <AppLayout>
                <PlaceholderScreen title="Portfolio" />
              </AppLayout>
            </ProtectedRoute>
          } />
          <Route path="/backtest" element={
            <ProtectedRoute>
              <AppLayout>
                <PlaceholderScreen title="Backtest" />
              </AppLayout>
            </ProtectedRoute>
          } />
          <Route path="/chat" element={
            <ProtectedRoute>
              <AppLayout>
                <PlaceholderScreen title="Chat" />
              </AppLayout>
            </ProtectedRoute>
          } />
          <Route path="/notifications" element={
            <ProtectedRoute>
              <AppLayout>
                <PlaceholderScreen title="Notifications" />
              </AppLayout>
            </ProtectedRoute>
          } />
          <Route path="/admin" element={
            <ProtectedRoute>
              <AppLayout>
                <PlaceholderScreen title="Admin" />
              </AppLayout>
            </ProtectedRoute>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
