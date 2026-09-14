import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { auth, setAuthToken, type UserResponse, type LoginData, type RegisterData } from '@investiq/api-client';

interface AuthContextType {
  user: UserResponse | null;
  isLoading: boolean;
  login: (data: LoginData) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initializeAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        setAuthToken(token);
        try {
          const userData = await auth.getMe();
          setUser(userData);
        } catch (error) {
          console.error('Failed to fetch user', error);
          logout();
        }
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (data: LoginData) => {
    const response = await auth.login(data);
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('refresh_token', response.refresh_token);
    setAuthToken(response.access_token);
    
    const userData = await auth.getMe();
    setUser(userData);
  };

  const register = async (data: RegisterData) => {
    await auth.register(data);
    // After register, automatically log in
    await login({ username: data.email, password: data.password });
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setAuthToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
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
