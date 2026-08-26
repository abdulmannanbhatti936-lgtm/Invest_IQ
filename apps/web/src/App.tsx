import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { healthCheck } from '@investiq/api-client';
import type { Placeholder } from '@investiq/shared-types';
import { colors } from '@investiq/design-tokens';
import i18next from '@investiq/i18n';
import { useEffect, useState } from 'react';

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
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PlaceholderScreen title="Home" />} />
        <Route path="/login" element={<PlaceholderScreen title="Login" />} />
        <Route path="/register" element={<PlaceholderScreen title="Register" />} />
        <Route path="/onboarding" element={<PlaceholderScreen title="Onboarding" />} />
        <Route path="/dashboard" element={<PlaceholderScreen title="Dashboard" />} />
        <Route path="/stocks" element={<PlaceholderScreen title="Stocks" />} />
        <Route path="/portfolio" element={<PlaceholderScreen title="Portfolio" />} />
        <Route path="/backtest" element={<PlaceholderScreen title="Backtest" />} />
        <Route path="/chat" element={<PlaceholderScreen title="Chat" />} />
        <Route path="/notifications" element={<PlaceholderScreen title="Notifications" />} />
        <Route path="/admin" element={<PlaceholderScreen title="Admin" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
