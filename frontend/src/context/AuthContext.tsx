import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from 'react';
import { User, AuthState } from '../types/auth';
import { authApi } from '../api/authApi';
import { useToast } from './ToastContext';

interface AuthContextValue extends AuthState {
  login: (credentials: { username: string; password: string }, turnstileToken?: string) => Promise<void>;
  signup: (payload: { username: string; password: string; email?: string }, turnstileToken?: string) => Promise<void>;
  logout: () => Promise<void>;
  demoLogin: (turnstileToken?: string) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const { success, error, info } = useToast();

  const refreshUser = useCallback(async () => {
    try {
      const data = await authApi.getMe();
      if (data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (err) {
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (credentials: { username: string; password: string }, turnstileToken?: string) => {
    setIsLoading(true);
    try {
      const res = await authApi.login(
        turnstileToken ? { ...credentials, turnstile_token: turnstileToken } : credentials
      );
      setUser(res.user);
      setIsAuthenticated(true);
      success(`Welcome back, ${res.user.username}!`, 'Login Successful');
    } catch (err: any) {
      error(err.message || 'Login failed. Please check credentials.', 'Authentication Error');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [success, error]);

  const signup = useCallback(async (payload: { username: string; password: string; email?: string }, turnstileToken?: string) => {
    setIsLoading(true);
    try {
      const res = await authApi.signup(
        turnstileToken ? { ...payload, turnstile_token: turnstileToken } : payload
      );
      setUser(res.user);
      setIsAuthenticated(true);
      success(`Account created for ${res.user.username}!`, 'Welcome to WhatToCook');
    } catch (err: any) {
      error(err.message || 'Sign up failed.', 'Registration Error');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [success, error]);

  const demoLogin = useCallback(async (turnstileToken?: string) => {
    setIsLoading(true);
    try {
      const res = await authApi.demoLogin(turnstileToken);
      setUser(res.user);
      setIsAuthenticated(true);
      success('Logged in with pre-stocked Chef pantry!', 'Demo Ready 🍳');
    } catch (err: any) {
      error(err.message || 'Demo login failed.', 'Error');
    } finally {
      setIsLoading(false);
    }
  }, [success, error]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
      setUser(null);
      setIsAuthenticated(false);
      info('You have been logged out.', 'Goodbye');
    } catch (err: any) {
      error('Logout failed.', 'Error');
    }
  }, [info, error]);

  // Stable context identity — auth state consumers only re-render on real changes.
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated,
      isLoading,
      login,
      signup,
      logout,
      demoLogin,
      refreshUser,
    }),
    [user, isAuthenticated, isLoading, login, signup, logout, demoLogin, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
