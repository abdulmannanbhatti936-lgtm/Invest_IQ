import type { ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Briefcase,
  History,
  LayoutDashboard,
  LineChart,
  LogOut,
  MessageSquare,
  ShieldCheck,
} from 'lucide-react';
import { useTranslation } from '@investiq/i18n';
import { useAuth } from '../../features/auth/AuthContext';
import { NotificationBell } from '../../features/notifications/NotificationBell';
import { LanguageToggle, toggleClasses } from '../LanguageToggle';
import { ThemeToggle } from '../ThemeToggle';
import { Wordmark } from '../Wordmark';

const NAV = [
  { key: 'dashboard', path: '/dashboard', icon: LayoutDashboard },
  { key: 'stocks', path: '/stocks', icon: LineChart },
  { key: 'portfolio', path: '/portfolio', icon: Briefcase },
  { key: 'backtest', path: '/backtest', icon: History },
  { key: 'chat', path: '/chat', icon: MessageSquare },
];

const sideItem = ({ isActive }: { isActive: boolean }) =>
  `relative flex min-h-10 items-center gap-4 rounded-control px-4 text-sm font-medium transition-colors duration-150 ${
    isActive
      ? 'bg-primary-tint text-primary before:absolute before:inset-y-2 before:start-0 before:w-1 before:rounded-full before:bg-primary'
      : 'text-muted hover:bg-sunken hover:text-ink'
  }`;

const tabItem = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-14 flex-1 flex-col items-center justify-center gap-2 text-xs font-medium ${
    isActive ? 'text-primary' : 'text-muted'
  }`;

export const AppLayout = ({ children }: { children: ReactNode }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const isAdmin = user?.role === 'admin';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const items = isAdmin ? [...NAV, { key: 'admin', path: '/admin', icon: ShieldCheck }] : NAV;

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-ink">
      <aside className="hidden w-64 shrink-0 flex-col border-e border-line bg-surface md:flex">
        <div className="flex h-16 items-center gap-2 px-6">
          <Link to="/dashboard" className="text-xl">
            <Wordmark />
          </Link>
          {isAdmin && (
            <span className="rounded-full border border-warning px-2 text-xs font-semibold text-warning">
              {t('common.adminBadge')}
            </span>
          )}
        </div>

        <nav aria-label={t('nav.label')} className="flex-1 overflow-y-auto px-4 py-4">
          <ul className="space-y-2">
            {items.map(({ key, path, icon: Icon }) => (
              <li key={path}>
                <NavLink to={path} className={sideItem}>
                  <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                  {t(`nav.${key}`)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-line p-4">
          <div className="flex items-center gap-4 px-2 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-tint font-bold text-primary">
              {user?.full_name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{user?.full_name}</p>
              <p className="truncate text-xs text-muted" dir="ltr">
                {user?.email}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="mt-2 flex min-h-10 w-full items-center gap-2 rounded-control px-2 text-sm font-medium text-muted transition-colors hover:bg-sunken hover:text-ink"
          >
            <LogOut className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
            {t('common.logout')}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="z-10 flex h-16 shrink-0 items-center justify-between gap-2 border-b border-line bg-surface px-4 md:justify-end md:px-8">
          <Link to="/dashboard" className="text-lg md:hidden">
            <Wordmark />
          </Link>
          <div className="flex items-center gap-2">
            {/* The chat screen has its own toggle beside the conversation (Design.md §6.5) */}
            {location.pathname !== '/chat' && <LanguageToggle />}
            <ThemeToggle />
            <NotificationBell />
            <button
              type="button"
              onClick={handleLogout}
              aria-label={t('common.logout')}
              title={t('common.logout')}
              className={`${toggleClasses} md:hidden`}
            >
              <LogOut className="h-5 w-5 rtl:-scale-x-100" aria-hidden="true" />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 pt-6 pb-24 md:px-8 md:pt-8 md:pb-8">
          {/* Keyed by route so each screen fades in once (Design.md §11, 200-300 ms) */}
          <div key={location.pathname} className="iq-page mx-auto w-full max-w-[1200px]">
            {children}
          </div>
        </main>

        {/* Phone-width navigation: a bottom tab bar (Design.md §14.2) */}
        <nav
          aria-label={t('nav.label')}
          className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-surface md:hidden"
        >
          {NAV.map(({ key, path, icon: Icon }) => (
            <NavLink key={path} to={path} className={tabItem}>
              <Icon className="h-5 w-5" aria-hidden="true" />
              {t(`nav.${key}`)}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
};
