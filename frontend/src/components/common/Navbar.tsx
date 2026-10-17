import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  ChefHat,
  ShoppingBag,
  Sparkles,
  LogIn,
  LogOut,
  User as UserIcon,
  Menu,
  X,
  Compass,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { usePantry } from '../../context/PantryContext';
import { StyledButton } from './StyledButton';
import { AIProviderSwitcher } from './AIProviderSwitcher';
import { useTranslation } from 'react-i18next';

export const Navbar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, logout, demoLogin } = useAuth();
  const { pantryIngredients } = usePantry();
  const { t } = useTranslation();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const pantryCount = pantryIngredients.length;

  const navLinks = [
    {
      to: '/recipes',
      label: t('nav.recipes'),
      icon: <Compass className="w-4 h-4" />,
    },
    {
      to: '/can-cook',
      label: t('nav.canCook'),
      icon: <ChefHat className="w-4 h-4" />,
      badge: pantryCount > 0 ? pantryCount : undefined,
    },
    {
      to: '/pantry',
      label: t('nav.pantry'),
      icon: <ShoppingBag className="w-4 h-4" />,
      badge: pantryCount > 0 ? pantryCount : undefined,
    },
    {
      to: '/ai-chef',
      label: t('nav.aiChef'),
      icon: <Sparkles className="w-4 h-4 text-amber-500" />,
      glow: true,
    },
  ];

  const isActive = (path: string) => {
    if (path === '/' && location.pathname === '/') return true;
    if (path !== '/' && location.pathname.startsWith(path)) return true;
    return false;
  };

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-stone-200/80 transition-all">
      <div className="max-w-7xl 2xl:max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand Logo */}
        <Link to="/" className="flex items-center gap-2.5 shrink-0 group">
          <div className="w-10 h-10 rounded-2xl bg-linear-to-tr/srgb from-brand-600 via-orange-500 to-amber-500 flex items-center justify-center text-white shadow-md shadow-brand-500/20 group-hover:scale-105 transition-transform duration-300">
            <ChefHat className="w-5 h-5" />
          </div>
          <div className="flex flex-col">
            <span className="font-extrabold text-stone-900 tracking-tight text-base sm:text-lg leading-tight flex items-center gap-1.5">
              WhatToCook
              <span className="text-[10px] uppercase font-black px-1.5 py-0.2 rounded-md bg-amber-100 text-amber-800 border border-amber-200">
                AI
              </span>
            </span>
            <span className="hidden lg:block text-[10px] text-stone-600 font-semibold tracking-wider uppercase">
              {t('nav.tagline')}
            </span>
          </div>
        </Link>

        {/* Desktop Nav Links */}
        <nav className="hidden sm:flex items-center gap-1 bg-stone-100/80 p-1 rounded-2xl border border-stone-200/60 h-11 box-border">
          {navLinks.map((link) => {
            const active = isActive(link.to);
            return (
              <Link
                key={link.to}
                to={link.to}
                style={{ height: '36px' }}
                className={`h-9 flex items-center justify-center gap-1.5 px-2.5 lg:px-3.5 rounded-xl text-xs font-bold transition-all relative select-none box-border leading-none ${
 active
 ? 'bg-white text-brand-600'
 : 'text-stone-600 hover:text-stone-900 hover:bg-stone-200/50'
 }`}
              >
                <span className="shrink-0 flex items-center justify-center">{link.icon}</span>
                <span className="leading-none whitespace-nowrap hidden lg:inline">{link.label}</span>
                {link.badge !== undefined && (
                  <span
                    className={`h-5 min-w-[20px] px-1.5 flex items-center justify-center text-[10px] leading-none rounded-full font-extrabold shrink-0 ${
 active ? 'bg-brand-100 text-brand-700' : 'bg-stone-200 text-stone-700'
 }`}
                  >
                    {link.badge}
                  </span>
                )}
                {link.glow && !active && (
                  <span className="absolute top-1 right-1 flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right Utility & Auth Area */}
        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0 min-w-0">
          <div className="hidden 2xl:block">
            <AIProviderSwitcher compact />
          </div>

          {/* User Auth Section */}
          {isAuthenticated ? (
            <div className="flex items-center gap-2 pl-2 border-l border-stone-200">
              <div className="flex items-center gap-2 px-2 py-1 rounded-xl bg-stone-50 border border-stone-200/80 text-xs font-bold text-stone-800">
                <div className="w-6 h-6 rounded-full bg-linear-to-tr/srgb from-brand-500 to-amber-500 text-white flex items-center justify-center font-extrabold text-[10px]">
                  {user?.username?.substring(0, 2).toUpperCase() || 'U'}
                </div>
                <span className="hidden xl:inline">{user?.username}</span>
              </div>
              <button
                onClick={() => logout()}
                title={t('nav.logout')}
                aria-label="Logout"
                className="p-1.5 rounded-xl text-stone-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 pl-2 border-l border-stone-200">
              <button
                onClick={() => demoLogin()}
                className="hidden xl:block px-3 py-1.5 rounded-xl text-xs font-bold text-stone-600 hover:text-stone-900 hover:bg-stone-100 transition-colors cursor-pointer"
              >
                {t('nav.guestDemo')}
              </button>
              <StyledButton
                $variant="primary"
                $size="sm"
                onClick={() => navigate('/auth')}
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>{t('nav.signIn')}</span>
              </StyledButton>
            </div>
          )}
        </div>

        {/* Mobile Menu Toggle Button */}
        <div className="flex sm:hidden items-center gap-2">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
            className="p-2 rounded-xl bg-stone-100 text-stone-700 hover:bg-stone-200 transition-colors cursor-pointer"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="sm:hidden glass-panel border-t border-stone-200 p-4 space-y-3">
          <div className="py-2">
            <AIProviderSwitcher />
          </div>

          <div className="space-y-1">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center justify-between p-3 rounded-xl text-sm font-semibold ${
 isActive(link.to)
 ? 'bg-brand-50 text-brand-600 font-bold'
 : 'text-stone-700 hover:bg-stone-100'
 }`}
              >
                <div className="flex items-center gap-2.5">
                  {link.icon}
                  <span>{link.label}</span>
                </div>
                {link.badge !== undefined && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-brand-100 text-brand-700 font-bold">
                    {link.badge}
                  </span>
                )}
              </Link>
            ))}
          </div>

          <div className="pt-3 border-t border-stone-200">
            {isAuthenticated ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <UserIcon className="w-4 h-4 text-stone-500" />
                  <span className="text-sm font-medium">{user?.username}</span>
                </div>
                <button
                  onClick={() => {
                    logout();
                    setMobileMenuOpen(false);
                  }}
                  className="text-xs text-rose-600 font-semibold hover:underline cursor-pointer"
                >
                  Logout
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <StyledButton
                  $variant="secondary"
                  $size="sm"
                  $fullWidth
                  onClick={() => {
                    demoLogin();
                    setMobileMenuOpen(false);
                  }}
                >
                  {t('nav.guestDemo')}
                </StyledButton>
                <StyledButton
                  $variant="primary"
                  $size="sm"
                  $fullWidth
                  onClick={() => {
                    navigate('/auth');
                    setMobileMenuOpen(false);
                  }}
                >
                  Sign In
                </StyledButton>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
