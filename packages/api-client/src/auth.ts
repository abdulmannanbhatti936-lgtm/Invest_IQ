import { apiClient } from './client';

export interface LoginData {
  username: string; // email in OAuth2 format
  password: string;
}

export interface RegisterData {
  email: string;
  full_name: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface RiskProfileResponse {
  id: string;
  user_id: string;
  category: string;
  answers: Record<string, any>;
  updated_at: string;
}

export const auth = {
  login: async (data: LoginData): Promise<TokenResponse> => {
    // OAuth2 expects form url-encoded data
    const formData = new URLSearchParams();
    formData.append('username', data.username);
    formData.append('password', data.password);
    
    const response = await apiClient.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  register: async (data: RegisterData): Promise<UserResponse> => {
    const response = await apiClient.post('/auth/register', data);
    return response.data;
  },

  getMe: async (): Promise<UserResponse> => {
    const response = await apiClient.get('/users/me');
    return response.data;
  },

  getRiskProfile: async (): Promise<RiskProfileResponse> => {
    const response = await apiClient.get('/users/me/risk-profile');
    return response.data;
  },

  saveRiskProfile: async (answers: Record<string, any>): Promise<RiskProfileResponse> => {
    const response = await apiClient.patch('/users/me/risk-profile', { answers });
    return response.data;
  },
};
