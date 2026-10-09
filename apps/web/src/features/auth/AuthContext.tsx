import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  auth,
  getErrorStatus,
  tokens,
  type LoginData,
  type RegisterData,
} from '@investiq/api-client';
import type { User } from '@investiq/shared-types';

export const SESSION_EXPIRED_EVENT = 'investiq:session-expired';
const ME_KEY = ['me'];

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  /** Set when loading the user failed for a reason other than auth (e.g. API down). */
  loadError: boolean;
  sessionExpired: boolean;
  login: (data: LoginData) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  retry: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const queryClient = useQueryClient();
  const [hasSession, setHasSession] = useState(tokens.hasSession());
  const [sessionExpired, setSessionExpired] = useState(false);

  const me = useQuery({
    queryKey: ME_KEY,
    queryFn: auth.getMe,
    enabled: hasSession,
    retry: (count, error) => getErrorStatus(error) !== 401 && count < 2,
    staleTime: 5 * 60 * 1000,
  });

  const endSession = useCallback(() => {
    tokens.clear();
    setHasSession(false);
    queryClient.clear();
  }, [queryClient]);

  // The API client fires this when a refresh token is rejected
  useEffect(() => {
    const onExpired = () => {
      endSession();
      setSessionExpired(true);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [endSession]);

  const login = async (data: LoginData) => {
    await auth.login(data);
    setSessionExpired(false);
    setHasSession(true);
    await queryClient.fetchQuery({ queryKey: ME_KEY, queryFn: auth.getMe });
  };

  const register = async (data: RegisterData) => {
    await auth.register(data);
    await login({ username: data.email, password: data.password });
  };

  const refreshUser = async () => {
    await queryClient.invalidateQueries({ queryKey: ME_KEY });
  };

  const loadError = hasSession && me.isError && getErrorStatus(me.error) !== 401;

  return (
    <AuthContext.Provider
      value={{
        user: hasSession ? (me.data ?? null) : null,
        isLoading: hasSession && me.isPending,
        loadError,
        sessionExpired,
        login,
        register,
        logout: () => {
          void auth.logout(); // revokes the refresh token server-side (best effort)
          endSession();
        },
        refreshUser,
        retry: () => void me.refetch(),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
