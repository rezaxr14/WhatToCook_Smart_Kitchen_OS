import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { ChefHat, ArrowRight, Sparkles } from 'lucide-react';

/** 404 for unknown routes. Authenticated chefs are sent to the catalog
 *  (they have no guest-landing); guests get a small rescue page instead of
 *  silently mounting the 3D journey at a fake URL. */
export const NotFoundPage: React.FC = () => {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-linear-to-br/srgb from-amber-400 to-orange-500 text-stone-950 shadow-[0_12px_40px_rgba(251,146,60,0.35)]">
        <ChefHat className="h-8 w-8" />
      </div>
      <div className="mt-8 text-[11px] font-black tracking-[0.5em] text-amber-600">404</div>
      <h1 className="mt-3 text-3xl font-black tracking-tight text-stone-900 sm:text-4xl">{t('notFound.title')}</h1>
      <p className="mt-3 max-w-md text-sm font-medium text-stone-500 sm:text-base">{t('notFound.sub')}</p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        {!user && (
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-full bg-linear-to-r/srgb from-amber-400 to-orange-500 px-6 py-3 text-sm font-extrabold text-stone-950 transition-transform hover:scale-105"
          >
            <Sparkles className="h-4 w-4" />
            {t('notFound.home')}
          </Link>
        )}
        <Link
          to="/recipes"
          className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white px-6 py-3 text-sm font-bold text-stone-700 transition-colors hover:border-stone-300 hover:text-stone-900"
        >
          {t('notFound.recipes')}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
};
