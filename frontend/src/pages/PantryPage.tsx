import React, { useState } from 'react';
import { Link } from 'react-router';
import {
  ShoppingBag,
  ChefHat,
  Sparkles,
  Camera,
  CheckCircle2,
  X,
  ScanLine,
  ArrowRight,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { usePantry } from '../context/PantryContext';
import { PantryShelf } from '../components/pantry/PantryShelf';
import { IngredientPicker } from '../components/pantry/IngredientPicker';
import { StyledButton } from '../components/common/StyledButton';

export const PantryPage: React.FC = () => {
  const { t } = useTranslation();
  const {
    pantryIngredients,
    availableIngredients,
    addIngredient,
    addMultipleIngredients,
    removeIngredient,
    clearPantry,
    openScanner,
    lastScanResult,
    dismissScanResult,
  } = usePantry();

  const [isConfirmingClear, setIsConfirmingClear] = useState(false);

  const handleClearWithConfirm = () => {
    if (isConfirmingClear) {
      clearPantry();
      setIsConfirmingClear(false);
    } else {
      setIsConfirmingClear(true);
      setTimeout(() => setIsConfirmingClear(false), 4000);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Page Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-linear-to-r/srgb from-stone-900 via-stone-850 to-stone-950 text-white rounded-3xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 end-0 w-80 h-80 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider mb-1">
            <ShoppingBag className="w-4 h-4" />
            <span>{t('pantryPage.inventoryBadge')}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">{t('pantryPage.title')}</h1>
          <p className="text-stone-400 text-sm mt-1 max-w-xl">
            {t('pantryPage.subtitle')}
          </p>
        </div>

        <div className="relative z-10 flex flex-wrap items-center gap-3">
          {/* Gemini Vision Fridge Scanner CTA */}
          <button
            onClick={openScanner}
            className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-linear-to-r/srgb from-amber-400 to-brand-500 text-stone-950 font-extrabold text-xs shadow-lg shadow-brand-500/20 hover:scale-105 transition-all cursor-pointer"
          >
            <Camera className="w-4 h-4" />
            <span>{t('pantryPage.scanFridgePhoto')}</span>
          </button>

          <Link to="/can-cook">
            <StyledButton $variant="primary" $size="md">
              <ChefHat className="w-4 h-4" />
              <span>{t('pantryPage.seeMatching')}</span>
            </StyledButton>
          </Link>

          <Link to="/ai-chef">
            <StyledButton $variant="sage" $size="md">
              <Sparkles className="w-4 h-4" />
              <span>{t('pantryPage.aiChefIdeas')}</span>
            </StyledButton>
          </Link>
        </div>
      </div>

      {/* Scanner spotlight — the fridge scanner is a headline feature, not a
          small icon tucked in the corner. */}
      <button
        type="button"
        onClick={openScanner}
        className="group relative w-full overflow-hidden rounded-3xl border border-amber-300/60 bg-linear-to-r/srgb from-amber-50 via-orange-50 to-amber-100 p-6 sm:p-8 shadow-lg shadow-amber-500/10 hover:shadow-xl hover:shadow-amber-500/20 transition-all cursor-pointer"
      >
        <div className="pointer-events-none absolute -end-12 -top-12 h-52 w-52 rounded-full bg-amber-300/40 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 start-1/3 h-40 w-40 rounded-full bg-brand-300/30 blur-3xl" />
        <div className="relative flex flex-col sm:flex-row sm:items-center gap-5">
          <div className="w-16 h-16 shrink-0 rounded-2xl bg-linear-to-br/srgb from-amber-400 to-brand-500 text-stone-950 flex items-center justify-center shadow-lg shadow-brand-500/25 group-hover:scale-105 transition-transform">
            <ScanLine className="w-8 h-8" />
          </div>
          <div className="min-w-0 flex-1 text-start">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight text-stone-900">
                {t('pantryPage.scanCardTitle')}
              </h2>
              <span className="rounded-full bg-stone-950 text-amber-300 text-[10px] font-black uppercase tracking-wider px-2 py-0.5">
                {t('pantryPage.scanCardBadge')}
              </span>
            </div>
            <p className="mt-1 text-sm text-stone-600 leading-relaxed max-w-2xl">
              {t('pantryPage.scanCardBody')}
            </p>
          </div>
          <span className="inline-flex shrink-0 items-center gap-2 rounded-2xl bg-stone-950 px-5 py-3 text-sm font-extrabold text-amber-200 shadow-lg group-hover:bg-stone-900 transition-colors">
            <Camera className="w-4 h-4" />
            {t('pantryPage.scanCardCta')}
            <ArrowRight className="w-4 h-4 rtl:rotate-180 transition-transform group-hover:translate-x-0.5" />
          </span>
        </div>
      </button>

      {/* Scan confirmation — the modal closes after a successful add, so the
          result must remain visible on the page. */}
      {lastScanResult && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900 shadow-xs"
        >
          <CheckCircle2 className="mt-0.5 w-5 h-5 shrink-0 text-emerald-600" />
          <div className="min-w-0 flex-1 text-start">
            <p className="text-sm font-extrabold">
              {t('pantryPage.scanAddedTitle', { count: lastScanResult.count })}
            </p>
            <p className="mt-0.5 text-xs font-medium text-emerald-700 break-words">
              {lastScanResult.names.join(', ')}
            </p>
            <Link
              to="/can-cook"
              className="mt-2 inline-flex items-center gap-1 text-xs font-extrabold text-emerald-800 hover:underline"
            >
              {t('pantryPage.scanAddedCta')}
              <ArrowRight className="w-3.5 h-3.5 rtl:rotate-180" />
            </Link>
          </div>
          <button
            type="button"
            onClick={dismissScanResult}
            aria-label={t('pantryPage.scanAddedDismiss')}
            className="shrink-0 rounded-full p-1.5 text-emerald-600 hover:bg-emerald-100 hover:text-emerald-800 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Pantry Shelf Section */}
      <div className="bg-white/80 backdrop-blur-xl border border-stone-200/90 rounded-3xl p-6 shadow-xs">
        <PantryShelf
          ingredients={pantryIngredients}
          onRemove={removeIngredient}
          onClear={handleClearWithConfirm}
          onOpenScanner={openScanner}
        />

        {isConfirmingClear && (
          <div className="mt-3 p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center justify-between">
            <span>{t('pantryPage.confirmClear')}</span>
            <div className="flex gap-2">
              <button
                onClick={clearPantry}
                className="px-3 py-1 bg-rose-600 text-white rounded-lg font-bold hover:bg-rose-700 transition-colors"
              >
                {t('pantryPage.yesClearAll')}
              </button>
              <button
                onClick={() => setIsConfirmingClear(false)}
                className="px-3 py-1 bg-stone-200 text-stone-700 rounded-lg hover:bg-stone-300 transition-colors"
              >
                {t('pantryPage.cancel')}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Add New Ingredients Section */}
      <IngredientPicker
        availableIngredients={availableIngredients}
        onAdd={addIngredient}
        onAddMultiple={addMultipleIngredients}
      />
    </div>
  );
};
