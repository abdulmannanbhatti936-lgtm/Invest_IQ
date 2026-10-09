import type { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Bell,
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
import { LanguageToggle } from '../LanguageToggle';

const NAV = [
  { key: 'dashboard', path: '/dashboard', icon: LayoutDashboard },
  { key: 'stocks', path: '/stocks', icon: LineChart },
  { key: 'portfolio', path: '/portfolio', icon: Briefcase },
  { key: 'backtest', path: '/backtest', icon: History },
  { key: 'chat', path: '/chat', icon: MessageSquare },
];

export const AppLayout = ({ children }: { children: ReactNode }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const isAdmin = user?.role === 'admin';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const items = isAdmin ? [...NAV, { key: 'admin', path: '/admin', icon: ShieldCheck }] : NAV;

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 text-gray-900">
      <aside className="hidden w-64 flex-col border-e border-gray-200 bg-white md:flex">
        <div className="flex h-16 items-center gap-2 border-b border-gray-200 px-6">
          <span className="text-xl font-bold tracking-tight text-blue-700">
            {t('common.appName')}
          </span>
          {isAdmin && (
            <span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-semibold text-purple-800">
              {t('common.adminBadge')}
            </span>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
          <ul className="space-y-1 px-3">
            {items.map(({ key, path, icon: Icon }) => (
              <li key={path}>
                <NavLink
                  to={path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-100'
                    }`
                  }
                >
                  <Icon className="h-5 w-5" />
                  {t(`nav.${key}`)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-gray-200 p-4">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 font-bold text-blue-700">
              {user?.full_name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-900">{user?.full_name}</p>
              <p className="truncate text-xs text-gray-500" dir="ltr">
                {user?.email}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="mt-2 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
          >
            <LogOut className="h-4 w-4 rtl:rotate-180" />
            {t('common.logout')}
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="z-10 flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 shadow-sm md:justify-end md:px-6">
          <span className="text-lg font-bold text-blue-700 md:hidden">{t('common.appName')}</span>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <NavLink
              to="/notifications"
              aria-label={t('nav.notifications')}
              className="rounded-md p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            >
              <Bell className="h-5 w-5" />
            </NavLink>
            <button
              type="button"
              onClick={handleLogout}
              aria-label={t('common.logout')}
              className="rounded-md p-2 text-gray-500 hover:bg-gray-100 md:hidden"
            >
              <LogOut className="h-5 w-5 rtl:rotate-180" />
            </button>
          </div>
        </header>

        {/* Mobile-width nav */}
        <nav className="flex gap-1 overflow-x-auto border-b border-gray-200 bg-white px-2 md:hidden">
          {items.map(({ key, path }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `shrink-0 px-3 py-2 text-sm font-medium ${
                  isActive ? 'border-b-2 border-blue-600 text-blue-700' : 'text-gray-600'
                }`
              }
            >
              {t(`nav.${key}`)}
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 overflow-y-auto p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
};
