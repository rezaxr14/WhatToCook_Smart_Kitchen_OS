import React from 'react';
import { ChefHat, Sparkles, Heart } from 'lucide-react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from './LanguageSwitcher';

export const Footer: React.FC = () => {
  const { t } = useTranslation();

  return (
    <footer className="bg-stone-900 text-stone-300 border-t border-stone-800 mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
          {/* Brand */}
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-linear-to-tr/srgb from-brand-500 to-amber-400 flex items-center justify-center text-white shadow-md">
                <ChefHat className="w-5 h-5" />
              </div>
              <span className="font-bold text-xl text-white tracking-tight">WhatToCook</span>
            </div>
            <p className="text-stone-400 text-sm leading-relaxed max-w-sm">
              {t('footer.blurb')}
            </p>
            <div className="flex items-center gap-2 text-xs font-semibold text-stone-300">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>Smart Cloud & Local AI Engine</span>
            </div>
          </div>

          {/* Quick Links */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-stone-200 uppercase tracking-wider">{t('footer.colProduct')}</h4>
            <ul className="space-y-2 text-sm text-stone-400 font-medium">
              <li>
                <Link to="/can-cook" className="hover:text-white transition-colors">
                  {t('nav.canCook')}
                </Link>
              </li>
              <li>
                <Link to="/ai-chef" className="hover:text-white transition-colors">
                  {t('nav.aiChef')}
                </Link>
              </li>
              <li>
                <Link to="/pantry" className="hover:text-white transition-colors">
                  {t('features.scannerT')}
                </Link>
              </li>
            </ul>
          </div>

          {/* Tech stack highlights */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-stone-200 uppercase tracking-wider">{t('footer.colTech')}</h4>
            <ul className="space-y-2 text-sm text-stone-400 font-medium">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-500" />
                <span>Django REST Framework</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                <span>React + Vite + TypeScript</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-sky-500" />
                <span>Smart Generative AI API</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-stone-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-stone-500">
          <p>© {new Date().getFullYear()} WhatToCook AI. {t('footer.rights')}</p>
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <p className="hidden sm:flex items-center gap-1">
              Made with <Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-500" /> for passionate home chefs everywhere.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};
