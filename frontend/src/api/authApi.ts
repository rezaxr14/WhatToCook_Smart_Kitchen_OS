import { apiClient } from './client';
import { User } from '../types/auth';
import { UserPantry } from '../types/pantry';

export interface AuthResponse {
  message?: string;
  user: User;
  pantry?: UserPantry;
}

export interface MeResponse {
  authenticated: boolean;
  user: User | null;
  pantry: UserPantry | null;
}

export interface ChallengeConfig {
  enabled: boolean;
  site_key: string;
  action: string;
  every_n: number;
  calls_since_verified: number;
}

/** Turnstile token is optional: it is only sent when the gate is configured. */
type ChallengeToken = { turnstile_token?: string };

export const authApi = {
  login: async (
    credentials: { username: string; password: string } & ChallengeToken
  ): Promise<AuthResponse> => {
    return apiClient<AuthResponse>('/api/auth/login/', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  signup: async (
    payload: { username: string; password: string; email?: string } & ChallengeToken
  ): Promise<AuthResponse> => {
    return apiClient<AuthResponse>('/api/auth/signup/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  logout: async (): Promise<{ message: string }> => {
    return apiClient<{ message: string }>('/api/auth/logout/', {
      method: 'POST',
    });
  },

  getMe: async (): Promise<MeResponse> => {
    return apiClient<MeResponse>('/api/auth/me/');
  },

  demoLogin: async (token?: string): Promise<AuthResponse> => {
    return apiClient<AuthResponse>('/api/auth/demo/', {
      method: 'POST',
      body: JSON.stringify(token ? { turnstile_token: token } : {}),
    });
  },

  getChallenge: async (): Promise<ChallengeConfig> => {
    return apiClient<ChallengeConfig>('/api/auth/challenge/');
  },

  verifyChallenge: async (token: string): Promise<{ verified: boolean }> => {
    return apiClient<{ verified: boolean }>('/api/auth/challenge/', {
      method: 'POST',
      body: JSON.stringify({ turnstile_token: token }),
    });
  },
};
