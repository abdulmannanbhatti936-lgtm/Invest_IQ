import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { configureApi, DEFAULT_API_URL } from '@investiq/api-client';
import '@investiq/i18n';
import App from './App.tsx';
import { SESSION_EXPIRED_EVENT } from './features/auth/AuthContext';
import { initLanguage } from './lib/language';
import { localTokenStorage } from './lib/tokenStorage';
import './index.css';

configureApi({
  baseURL: import.meta.env.VITE_API_URL || DEFAULT_API_URL,
  tokenStorage: localTokenStorage,
  onSessionExpired: () => window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT)),
});
initLanguage();

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 60 * 1000 } },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
