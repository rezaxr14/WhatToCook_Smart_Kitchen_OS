import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChefHat, LogIn, UserPlus, Zap } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { StyledButton } from '../components/common/StyledButton';
import { StyledCard } from '../components/common/StyledCard';

export const AuthPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login, signup, demoLogin, isLoading } = useAuth();

  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');

    try {
      if (mode === 'login') {
        await login({ username, password });
      } else {
        await signup({ username, password, email });
      }
      navigate('/');
    } catch (err: any) {
      setErrorMessage(err.message || t('auth.authFailed'));
    }
  };

  const handleDemo = async () => {
    try {
      await demoLogin();
      navigate('/');
    } catch (err: any) {
      setErrorMessage(t('auth.demoFailed'));
    }
  };

  return (
    <div className="max-w-md mx-auto py-12 px-4">
      <StyledCard className="p-8 bg-white border border-stone-200 shadow-xl space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-2xl bg-linear-to-tr/srgb from-brand-600 to-amber-400 flex items-center justify-center text-white mx-auto shadow-md shadow-brand-500/30">
            <ChefHat className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-extrabold text-stone-900 tracking-tight">
            {mode === 'login' ? t('auth.welcomeBack') : t('auth.joinTitle')}
          </h2>
          <p className="text-stone-500 text-xs">
            {mode === 'login'
              ? t('auth.loginSub')
              : t('auth.signupSub')}
          </p>
        </div>

        {/* 1-Click Guest Demo Button */}
        <button
          type="button"
          onClick={handleDemo}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-linear-to-r/srgb from-amber-500/10 via-brand-500/10 to-orange-500/10 border border-amber-300 text-stone-800 font-bold text-sm hover:border-brand-500 transition-all shadow-xs group"
        >
          <Zap className="w-4 h-4 text-amber-600 fill-amber-500 group-hover:scale-110 transition-transform" />
          <span>{t('auth.guestDemo')}</span>
        </button>

        <div className="relative flex py-1 items-center">
          <div className="grow border-t border-stone-200"></div>
          <span className="shrink mx-4 text-xs uppercase font-bold text-stone-400">{t('auth.orWithAccount')}</span>
          <div className="grow border-t border-stone-200"></div>
        </div>

        {/* Tabs */}
        <div className="flex rounded-xl bg-stone-100 p-1">
          <button
            type="button"
            onClick={() => setMode('login')}
            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
 mode === 'login' ? 'bg-white text-stone-900 shadow-xs' : 'text-stone-500 hover:text-stone-900'
 }`}
          >
            {t('auth.signInTab')}
          </button>
          <button
            type="button"
            onClick={() => setMode('signup')}
            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
 mode === 'signup' ? 'bg-white text-stone-900 shadow-xs' : 'text-stone-500 hover:text-stone-900'
 }`}
          >
            {t('auth.createAccountTab')}
          </button>
        </div>

        {/* Error message */}
        {errorMessage && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold">
            {errorMessage}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1">{t('auth.username')}</label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('auth.usernamePlaceholder')}
              className="w-full px-3.5 py-2.5 bg-stone-50 border border-stone-200 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>

          {mode === 'signup' && (
            <div>
              <label className="block text-xs font-semibold text-stone-700 mb-1">
                {t('auth.email')} <span className="text-stone-400 font-normal">{t('auth.optional')}</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="chef@example.com"
                className="w-full px-3.5 py-2.5 bg-stone-50 border border-stone-200 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1">{t('auth.password')}</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 bg-stone-50 border border-stone-200 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>

          <StyledButton
            $variant="primary"
            $size="md"
            $fullWidth
            type="submit"
            disabled={isLoading}
            className="mt-2"
          >
            {mode === 'login' ? (
              <>
                <LogIn className="w-4 h-4" />
                <span>{t('auth.loginCta')}</span>
              </>
            ) : (
              <>
                <UserPlus className="w-4 h-4" />
                <span>{t('auth.signupCta')}</span>
              </>
            )}
          </StyledButton>
        </form>
      </StyledCard>
    </div>
  );
};
