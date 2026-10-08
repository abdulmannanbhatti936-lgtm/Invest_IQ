import type {
  OnboardingProgress,
  RiskAnswers,
  RiskProfile,
  RiskQuestion,
  TokenPair,
  User,
} from '@investiq/shared-types';
import { apiClient, tokens } from './client';

export interface LoginData {
  username: string; // email, per the OAuth2 password form
  password: string;
}

export interface RegisterData {
  email: string;
  full_name: string;
  password: string;
}

export const auth = {
  login: async (data: LoginData): Promise<TokenPair> => {
    const form = new URLSearchParams();
    form.append('username', data.username);
    form.append('password', data.password);
    const response = await apiClient.post<TokenPair>('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    tokens.set(response.data);
    return response.data;
  },

  register: async (data: RegisterData): Promise<User> => {
    const response = await apiClient.post<User>('/auth/register', data);
    return response.data;
  },

  /** Ends the session locally at once, then revokes the refresh token on the server. */
  logout: async (): Promise<void> => {
    const refreshToken = tokens.refreshToken();
    tokens.clear();
    if (!refreshToken) return;
    try {
      await apiClient.post('/auth/logout', { refresh_token: refreshToken }, { timeout: 5000 });
    } catch {
      // Offline or API down: the user is still logged out here, and the token expires on its own
    }
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/users/me');
    return response.data;
  },
};

export const riskProfileApi = {
  /** The questionnaire is defined once, on the server (ids + option values; labels are i18n). */
  getQuestionnaire: async (): Promise<RiskQuestion[]> => {
    const response = await apiClient.get<RiskQuestion[]>('/users/risk-questionnaire');
    return response.data;
  },

  get: async (): Promise<RiskProfile> => {
    const response = await apiClient.get<RiskProfile>('/users/me/risk-profile');
    return response.data;
  },

  save: async (answers: RiskAnswers): Promise<RiskProfile> => {
    const response = await apiClient.patch<RiskProfile>('/users/me/risk-profile', { answers });
    return response.data;
  },

  getProgress: async (): Promise<OnboardingProgress | null> => {
    const response = await apiClient.get<OnboardingProgress | null>(
      '/users/me/onboarding-progress',
    );
    return response.data;
  },

  saveProgress: async (progress: OnboardingProgress): Promise<OnboardingProgress> => {
    const response = await apiClient.put<OnboardingProgress>(
      '/users/me/onboarding-progress',
      progress,
    );
    return response.data;
  },
};
